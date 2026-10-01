"""Authority-backed history and route constraints for Operation Pancake decisions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

GUARD_VERSION = 1
CONSTRAINT_STATUSES = {"REQUIRED_NEXT", "REJECTED"}


class AuthorityGuardError(RuntimeError):
    """Raised when the authoritative decision guard is missing or malformed."""


@dataclass(frozen=True)
class RouteConstraint:
    id: str
    mission_id: str
    route_id: str
    status: str
    description: str
    source: str

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> "RouteConstraint":
        values = {
            "id": str(raw.get("id", "")).strip(),
            "mission_id": str(raw.get("mission_id", "")).strip(),
            "route_id": str(raw.get("route_id", "")).strip(),
            "status": str(raw.get("status", "")).strip().upper(),
            "description": str(raw.get("description", "")).strip(),
            "source": str(raw.get("source", "")).strip(),
        }
        missing = [key for key in ("id", "mission_id", "route_id", "description", "source") if not values[key]]
        if missing:
            raise AuthorityGuardError("AUTHORITY_GUARD_MALFORMED: missing " + ", ".join(missing))
        if values["status"] not in CONSTRAINT_STATUSES:
            raise AuthorityGuardError(
                "AUTHORITY_GUARD_MALFORMED: unsupported status "
                + (values["status"] or "<missing>")
            )
        return cls(**values)

    def evidence_item(self) -> dict[str, str]:
        return {
            "kind": "VERIFIED_HISTORY",
            "text": (
                f"Authoritative route constraint {self.id}: route {self.route_id} "
                f"is {self.status}. {self.description}"
            ),
            "fact_key": f"authority_route:{self.route_id}",
            "fact_value": self.status,
            "source": self.source,
        }


@dataclass(frozen=True)
class AuthorityGuardSnapshot:
    authority_revision: int
    active_mission_id: str
    constraints: tuple[RouteConstraint, ...]
    fingerprint: str

    @property
    def required_next_routes(self) -> tuple[str, ...]:
        return tuple(
            item.route_id for item in self.constraints if item.status == "REQUIRED_NEXT"
        )

    @property
    def rejected_routes(self) -> tuple[str, ...]:
        return tuple(
            item.route_id for item in self.constraints if item.status == "REJECTED"
        )

    def evidence_items(self) -> list[dict[str, str]]:
        return [item.evidence_item() for item in self.constraints]

    def context(self) -> dict[str, Any]:
        return {
            "authority_revision": self.authority_revision,
            "active_mission_id": self.active_mission_id,
            "fingerprint": self.fingerprint,
            "required_next_routes": list(self.required_next_routes),
            "rejected_routes": list(self.rejected_routes),
            "constraints": [asdict(item) for item in self.constraints],
        }

    def decision_errors(
        self,
        *,
        selected_route_id: str | None,
        remaining_route_ids: tuple[str, ...],
        user_action_required: bool,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        selected = (selected_route_id or "").strip()
        remaining = tuple(dict.fromkeys(x.strip() for x in remaining_route_ids if x.strip()))
        required = self.required_next_routes
        rejected = set(self.rejected_routes)

        if self.constraints and not selected:
            errors.append("AUTHORITY_ROUTE_ID_REQUIRED")
        if selected and selected in rejected:
            errors.append(f"AUTHORITY_ROUTE_REJECTED:{selected}")
        rejected_remaining = sorted(set(remaining) & rejected)
        if rejected_remaining:
            errors.extend(f"AUTHORITY_ROUTE_REJECTED:{route}" for route in rejected_remaining)

        if required:
            if selected not in required:
                errors.append(
                    "AUTHORITATIVE_REQUIRED_ROUTE_NOT_SELECTED:" + "|".join(required)
                )
            missing = [
                route for route in required
                if route != selected and route not in remaining
            ]
            if missing:
                errors.append(
                    "AUTHORITATIVE_REQUIRED_ROUTE_OMITTED:" + "|".join(missing)
                )
            if user_action_required:
                errors.append(
                    "USER_ACTION_BLOCKED_BY_AUTHORITATIVE_ROUTE:" + "|".join(required)
                )
        return tuple(dict.fromkeys(errors))


def load_authority_guard(
    authority_path: Path | None,
    mission: str,
    *,
    required: bool = False,
) -> AuthorityGuardSnapshot | None:
    if authority_path is None:
        if required:
            raise AuthorityGuardError("AUTHORITY_GUARD_REQUIRED")
        return None
    try:
        payload = json.loads(Path(authority_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuthorityGuardError(
            f"AUTHORITY_GUARD_UNAVAILABLE:{type(exc).__name__}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise AuthorityGuardError("AUTHORITY_GUARD_MALFORMED: authority root is not an object")

    revision = payload.get("state_revision")
    active = payload.get("active_mission")
    active_mission_id = (
        str(active.get("id", "")).strip() if isinstance(active, Mapping) else ""
    )
    if not isinstance(revision, int) or revision <= 0 or not active_mission_id:
        raise AuthorityGuardError("AUTHORITY_GUARD_MALFORMED: invalid authority identity")
    if required and active_mission_id != mission:
        raise AuthorityGuardError(
            f"AUTHORITY_MISSION_MISMATCH:{active_mission_id}!={mission}"
        )

    guard = payload.get("decision_guard")
    if guard is None:
        if required:
            raise AuthorityGuardError("AUTHORITY_GUARD_REQUIRED")
        raw_constraints: list[Any] = []
        version = GUARD_VERSION
    elif not isinstance(guard, Mapping):
        raise AuthorityGuardError("AUTHORITY_GUARD_MALFORMED: decision_guard is not an object")
    else:
        version = guard.get("version")
        if version != GUARD_VERSION:
            raise AuthorityGuardError(
                f"AUTHORITY_GUARD_MALFORMED: unsupported version {version!r}"
            )
        raw_constraints = guard.get("constraints", [])
        if not isinstance(raw_constraints, list):
            raise AuthorityGuardError(
                "AUTHORITY_GUARD_MALFORMED: constraints must be a list"
            )

    constraints: list[RouteConstraint] = []
    seen_ids: set[str] = set()
    route_statuses: dict[str, set[str]] = {}
    for raw in raw_constraints:
        if not isinstance(raw, Mapping):
            raise AuthorityGuardError(
                "AUTHORITY_GUARD_MALFORMED: constraint must be an object"
            )
        item = RouteConstraint.from_raw(raw)
        if item.id in seen_ids:
            raise AuthorityGuardError(
                f"AUTHORITY_GUARD_MALFORMED: duplicate constraint id {item.id}"
            )
        seen_ids.add(item.id)
        if item.mission_id not in {mission, "*"}:
            continue
        constraints.append(item)
        route_statuses.setdefault(item.route_id, set()).add(item.status)

    conflicts = sorted(
        route for route, statuses in route_statuses.items() if len(statuses) > 1
    )
    if conflicts:
        raise AuthorityGuardError(
            "AUTHORITY_GUARD_CONTRADICTION:" + "|".join(conflicts)
        )

    canonical = {
        "authority_revision": revision,
        "active_mission_id": active_mission_id,
        "mission": mission,
        "version": version,
        "constraints": [asdict(item) for item in constraints],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AuthorityGuardSnapshot(
        authority_revision=revision,
        active_mission_id=active_mission_id,
        constraints=tuple(constraints),
        fingerprint=fingerprint,
    )
