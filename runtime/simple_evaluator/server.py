"""Tiny local server for Simple Evaluator and its user-started browser watches."""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import webbrowser
import hashlib
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

from file_lock import exclusive_file_lock
from release_info import load_release
from operations import (
    AUDIT_SCHEMA,
    build_audit,
    create_support_bundle,
    read_recent_jsonl,
    record_event,
    write_audit,
)
from maintenance import STABILITY_SCHEMA, evaluate_stability, write_stability_report
from catalog_import import validate_feed as validate_catalog_feed, merge_catalog
from authorized_market_bridge import DEFAULT_CONFIG as AUTHORIZED_MARKET_CONFIG, load_config as load_authorized_market_config
from background_watch import (
    ALERTS,
    RUNTIME,
    run_once as run_authorized_market_once,
    mark_unavailable as mark_authorized_market_unavailable,
    write_runtime_status as write_authorized_runtime_status,
    DEFAULT_ALERTS,
    DEFAULT_RUNTIME,
    DEFAULT_STATE,
    backup_path,
    merge_observations,
    process_payload,
    read_json,
    write_json_atomic,
)



class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Use exclusive localhost binds so Windows never shares a port with another listener."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


ROOT = Path(__file__).resolve().parent
FEED = ROOT / "market-feed.json"
STATE = ROOT / "app-state.json"
CARDS = ROOT / "cards.json"
CATALOG_SOURCE = ROOT / "catalog-source.json"
CATALOG_LOCAL_FEED = ROOT / "catalog-feed.json"
CATALOG_REFRESH_LOCK = ROOT / ".catalog-refresh.lock"
CATALOG_REFRESH_INTERVAL_HOURS = 24
MAX_CATALOG_FEED_BYTES = 25_000_000
CATALOG_SOURCE_SCHEMA = "simple-evaluator-catalog-source-v1"
DEFAULT_FEED = {"source_status": "NOT_CONNECTED", "observations": []}
MAX_STATE_BYTES = 5_000_000
MAX_BROWSER_OBSERVATION_BYTES = 50_000
MAX_OPERATIONAL_BACKUP_BYTES = 10_000_000
BACKUP_DIR = ROOT / "backups"
OPERATIONAL_BACKUP_SCHEMA = "simple-evaluator-operational-backup-v1"
DIAGNOSTICS_SCHEMA = "simple-evaluator-diagnostics-v1"
STATE_LOCK = ROOT / ".app-state.lock"
BROWSER_HELPER = ROOT / "browser-helper"
BROWSER_PROFILE_ROOT = ROOT / "browser-profile"
CFB_LOGIN_URL = "https://cfb.fan/prices/"
BROWSER_WATCH_INTERVAL_SECONDS = 120
BROWSER_CONFIG_SCHEMA = "simple-evaluator-browser-watch-config-v1"
BROWSER_WORK_QUEUE_SCHEMA = "simple-evaluator-browser-work-queue-v1"
BROWSER_WORK_TAB_FRAGMENT = "#simple-evaluator-worktab"
BROWSER_NORMAL_SEARCH_URL = "https://cfb.fan/27/players/#simple-evaluator-worktab"
BROWSER_OBSERVATION_SCHEMA = "simple-evaluator-browser-observation-v1"
VALUE_PROBE_SCHEMA = "simple-evaluator-value-probe-v1"
BROWSER_HEARTBEAT_SCHEMA = "simple-evaluator-browser-helper-heartbeat-v1"
BROWSER_HEARTBEAT = ROOT / "browser-helper-heartbeat.json"
BROWSER_HEARTBEAT_MAX_AGE_SECONDS = 180
MAX_BROWSER_HEARTBEAT_BYTES = 10_000
RELEASE = load_release()
RELEASE_ID = str(RELEASE.get("release") or "3T")
RELEASE_VERSION = str(RELEASE.get("version") or "1.2.0")
RELEASE_STATUS = str(RELEASE.get("status") or "FROZEN_PENDING_PHYSICAL_ACCEPTANCE")
PRODUCTION_ACCEPTANCE = ROOT / str(RELEASE.get("acceptance_file") or f"PRODUCTION_WORKSTATION_ACCEPTANCE_{RELEASE_ID}.json")
PRODUCTION_ACCEPTANCE_SCHEMA = "simple-evaluator-production-acceptance-v1"
OPERATIONS_DIR = ROOT / "operations"
OPERATION_LOG = OPERATIONS_DIR / "operational-events.jsonl"
AUDIT_HISTORY = OPERATIONS_DIR / "audit-history.jsonl"
LATEST_AUDIT = ROOT / str(RELEASE.get("operational_audit_file") or "operations/LATEST_OPERATIONAL_AUDIT.json")
SUPPORT_BUNDLE_DIR = ROOT / str(RELEASE.get("support_bundle_dir") or "support-bundles")
LATEST_STABILITY = ROOT / str(RELEASE.get("stability_report_file") or "operations/LATEST_STABILITY_REPORT.json")
STABILITY_HISTORY = OPERATIONS_DIR / "stability-history.jsonl"
VALUE_PROBE_LAST_STATUS: dict = {"status": "IDLE"}
VALUE_PROBE_RATE_LIMIT_KEY = "value_probe_rate_limit"
VALUE_PROBE_STATUS_KEY = "value_probe_status"
VALUE_PROBE_CARD_TIMEOUT_SECONDS = 60
VALUE_PROBE_TERMINAL_STATUSES = {"RATE_LIMITED", "TIMED_OUT", "SOURCE_UNAVAILABLE", "INTERRUPTED", "CANCELLED", "COMPLETED"}

def _value_probe_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _probe_status_from_state(state: dict) -> dict | None:
    raw = state.get(VALUE_PROBE_STATUS_KEY) if isinstance(state, dict) else None
    return raw if isinstance(raw, dict) else None

def _set_probe_status_in_state(state: dict, status: str, **fields) -> dict:
    global VALUE_PROBE_LAST_STATUS
    payload = {"status": status, "updated_at": _value_probe_now(), **fields}
    state[VALUE_PROBE_STATUS_KEY] = payload
    VALUE_PROBE_LAST_STATUS = dict(payload)
    return payload

def _active_value_probe_rate_limit(state: dict) -> dict | None:
    raw = state.get(VALUE_PROBE_RATE_LIMIT_KEY) if isinstance(state, dict) else None
    if not isinstance(raw, dict) or raw.get("active") is not True:
        return None
    return raw

def clear_value_probe_rate_limit() -> dict:
    global VALUE_PROBE_LAST_STATUS
    ensure_state()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        state.pop(VALUE_PROBE_RATE_LIMIT_KEY, None)
        current = _probe_status_from_state(state)
        if current and current.get("status") == "RATE_LIMITED":
            _set_probe_status_in_state(state, "IDLE", completed=0, total=0)
        write_json_atomic(STATE, state)
    VALUE_PROBE_LAST_STATUS = {"status": "IDLE"}
    return {"schema": VALUE_PROBE_SCHEMA, "ok": True, "rate_limited": False, "status": "IDLE"}


def _ensure_json(path: Path, fallback: dict) -> None:
    if path.exists():
        return
    if backup_path(path).exists():
        read_json(path, fallback)
        if path.exists():
            return
    write_json_atomic(path, fallback, backup_existing=False)


def ensure_feed() -> None:
    _ensure_json(FEED, DEFAULT_FEED)


def ensure_state() -> None:
    _ensure_json(STATE, DEFAULT_STATE)


def ensure_alerts() -> None:
    _ensure_json(ALERTS, DEFAULT_ALERTS)


def authorized_market_refresh() -> dict:
    """Run one refresh only through an expressly authorized market source.

    The source contract is intentionally fail-closed. A missing or invalid
    authorization config never falls back to CFB.FAN browser automation.
    """
    if not AUTHORIZED_MARKET_CONFIG.exists():
        raise PermissionError(
            "No authorized automated market source is configured. Provider express permission is required before automated Training Watch collection."
        )
    config = load_authorized_market_config(AUTHORIZED_MARKET_CONFIG)
    try:
        result = run_authorized_market_once(
            config, CARDS, STATE, FEED, ALERTS, runtime_path=RUNTIME, native_alerts=True
        )
    except Exception as exc:
        try:
            mark_authorized_market_unavailable(FEED, str(exc))
            write_authorized_runtime_status(RUNTIME, config, "MARKET_SOURCE_UNAVAILABLE", error=str(exc))
        except Exception:
            pass
        raise
    return {
        "schema": "simple-evaluator-authorized-market-refresh-v1",
        "ok": True,
        "authorization_basis": config.get("authorization_basis"),
        "authorization_reference": config.get("authorization_reference"),
        "provider_name": config.get("provider_name"),
        **result,
    }



def load_cards() -> list[dict]:
    raw = json.loads(CARDS.read_text(encoding="utf-8"))
    cards = raw.get("cards") if isinstance(raw, dict) else None
    if not isinstance(cards, list):
        raise ValueError("cards.json is invalid")
    return [c for c in cards if isinstance(c, dict) and isinstance(c.get("id"), str)]



class CatalogSourceRequired(RuntimeError):
    pass


def _catalog_doc() -> dict:
    raw = json.loads(CARDS.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cards"), list):
        raise ValueError("cards.json is invalid")
    return raw


def _parse_catalog_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip() or value.strip().upper() == "UNKNOWN":
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def catalog_source_config() -> dict:
    if not CATALOG_SOURCE.exists():
        return {
            "schema": CATALOG_SOURCE_SCHEMA,
            "configured": False,
            "enabled": False,
            "authorized": False,
            "url": None,
            "description": None,
        }
    try:
        raw = json.loads(CATALOG_SOURCE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema": CATALOG_SOURCE_SCHEMA,
            "configured": True,
            "enabled": False,
            "authorized": False,
            "url": None,
            "description": None,
            "error": f"catalog-source.json is invalid: {exc}",
        }
    if not isinstance(raw, dict):
        return {
            "schema": CATALOG_SOURCE_SCHEMA,
            "configured": True,
            "enabled": False,
            "authorized": False,
            "url": None,
            "description": None,
            "error": "catalog-source.json must contain an object",
        }
    url = str(raw.get("url") or "").strip()
    parsed = urlsplit(url) if url else None
    authorized = raw.get("authorized") is True
    enabled = raw.get("enabled") is True
    error = None
    if url and (parsed is None or parsed.scheme.lower() != "https" or not parsed.netloc):
        error = "catalog source URL must be HTTPS"
        enabled = False
    if enabled and not authorized:
        error = "catalog source must be explicitly marked authorized"
        enabled = False
    return {
        "schema": CATALOG_SOURCE_SCHEMA,
        "configured": True,
        "enabled": enabled,
        "authorized": authorized,
        "url": url or None,
        "description": str(raw.get("description") or "").strip() or None,
        "error": error,
    }


def catalog_status_payload() -> dict:
    doc = _catalog_doc()
    provenance = dict(doc.get("provenance") or {})
    source = catalog_source_config()
    now = datetime.now(timezone.utc)
    last_success = _parse_catalog_time(provenance.get("catalog_last_successful_refresh_at"))
    observed = _parse_catalog_time(provenance.get("latest_catalog_observed_at"))
    next_due = last_success + timedelta(hours=CATALOG_REFRESH_INTERVAL_HOURS) if last_success else None
    due = next_due is None or now >= next_due
    local_feed_available = CATALOG_LOCAL_FEED.exists()
    can_auto_update = bool(local_feed_available or (source.get("enabled") and source.get("authorized") and source.get("url")))
    refresh_age_hours = (now - last_success).total_seconds() / 3600 if last_success else None
    source_age_hours = (now - observed).total_seconds() / 3600 if observed else None
    fresh = bool(last_success and observed and refresh_age_hours <= CATALOG_REFRESH_INTERVAL_HOURS and source_age_hours <= CATALOG_REFRESH_INTERVAL_HOURS)
    return {
        "schema": "simple-evaluator-catalog-status-v1",
        "checked_at": _utc_now(),
        "card_count": len(doc["cards"]),
        "status": "FRESH" if fresh else "STALE",
        "daily_interval_hours": CATALOG_REFRESH_INTERVAL_HOURS,
        "due": bool(due),
        "can_auto_update": can_auto_update,
        "local_feed_available": local_feed_available,
        "source_config": source,
        "last_successful_refresh_at": provenance.get("catalog_last_successful_refresh_at"),
        "latest_catalog_source": provenance.get("latest_catalog_source") or provenance.get("description"),
        "latest_catalog_observed_at": provenance.get("latest_catalog_observed_at") or provenance.get("snapshot_timestamp"),
        "catalog_completeness": provenance.get("catalog_completeness") or "UNKNOWN",
        "source_claims_complete": bool(provenance.get("catalog_source_claims_complete", False)),
        "next_due_at": next_due.isoformat().replace("+00:00", "Z") if next_due else None,
        "refresh_age_hours": round(refresh_age_hours, 3) if refresh_age_hours is not None else None,
        "source_age_hours": round(source_age_hours, 3) if source_age_hours is not None else None,
    }


def _read_catalog_feed_from_source() -> dict:
    if CATALOG_LOCAL_FEED.exists():
        raw = CATALOG_LOCAL_FEED.read_bytes()
        if not raw or len(raw) > MAX_CATALOG_FEED_BYTES:
            raise ValueError("catalog-feed.json is empty or too large")
        return validate_catalog_feed(json.loads(raw.decode("utf-8")))
    config = catalog_source_config()
    if not (config.get("enabled") and config.get("authorized") and config.get("url")):
        raise CatalogSourceRequired("No authorized daily catalog source is configured")
    req = Request(
        str(config["url"]),
        headers={"User-Agent": f"Simple-Evaluator/{RELEASE_VERSION} authorized-catalog-refresh", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=15) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_CATALOG_FEED_BYTES:
                raise ValueError("catalog source response is too large")
            raw = response.read(MAX_CATALOG_FEED_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"catalog source request failed: {exc}") from exc
    if len(raw) > MAX_CATALOG_FEED_BYTES:
        raise ValueError("catalog source response is too large")
    return validate_catalog_feed(json.loads(raw.decode("utf-8")))


def apply_catalog_feed(feed: dict, *, trigger: str) -> dict:
    clean = validate_catalog_feed(feed)
    with exclusive_file_lock(CATALOG_REFRESH_LOCK):
        base = _catalog_doc()
        before_cards = base.get("cards", [])
        merged, stats = merge_catalog(base, clean)
        changed = merged.get("cards", []) != before_cards
        now = _utc_now()
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "catalog_last_successful_refresh_at": now,
            "catalog_last_refresh_trigger": str(trigger)[:80],
            "catalog_refresh_interval_hours": CATALOG_REFRESH_INTERVAL_HOURS,
            "latest_catalog_source": clean["source"],
            "latest_catalog_observed_at": clean["observed_at"],
            "catalog_source_claims_complete": bool(clean.get("complete", False)),
            "catalog_completeness": "SOURCE-CLAIMED COMPLETE" if clean.get("complete") else "UNKNOWN unless source explicitly establishes completeness",
            "source_card_count": len(merged.get("cards", [])),
        })
        merged["provenance"] = provenance
        write_json_atomic(CARDS, merged)
    result = {
        "schema": "simple-evaluator-catalog-refresh-v1",
        "ok": True,
        "changed": bool(changed),
        "added": stats.get("added", 0),
        "updated": stats.get("updated", 0),
        "total": stats.get("total", len(merged.get("cards", []))),
        "source": clean["source"],
        "observed_at": clean["observed_at"],
        "complete": bool(clean.get("complete", False)),
        "refreshed_at": now,
        "trigger": str(trigger)[:80],
    }
    record_event(OPERATION_LOG, "catalog_refresh", release=RELEASE_ID, version=RELEASE_VERSION, details=result)
    return result


def refresh_catalog(*, force: bool = False, trigger: str = "manual") -> dict:
    status = catalog_status_payload()
    if not force and not status.get("due"):
        return {"schema": "simple-evaluator-catalog-refresh-v1", "ok": True, "changed": False, "skipped": "NOT_DUE", "status": status}
    feed = _read_catalog_feed_from_source()
    return apply_catalog_feed(feed, trigger=trigger)


def rendered_app_html() -> bytes:
    template = (ROOT / "Simple-Evaluator.html").read_text(encoding="utf-8")
    marker = '<script id="card-data" type="application/json">'
    start = template.find(marker)
    if start < 0:
        raise ValueError("Simple-Evaluator.html card-data marker is missing")
    content_start = start + len(marker)
    end = template.find("</script>", content_start)
    if end < 0:
        raise ValueError("Simple-Evaluator.html card-data closing tag is missing")
    current = json.dumps(_catalog_doc(), separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return (template[:content_start] + current + template[end:]).encode("utf-8")


def normalize_source_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return ""
    if parsed.scheme.lower() != "https" or parsed.netloc.lower() != "cfb.fan":
        return ""
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return f"https://cfb.fan{path}"


def card_for_source_url(page_url: str, cards: list[dict] | None = None) -> dict | None:
    wanted = normalize_source_url(page_url)
    if not wanted:
        return None
    for card in cards or load_cards():
        if normalize_source_url(card.get("source", "")) == wanted:
            return card
    return None


def _watch_is_active(candidate: dict, now: datetime | None = None) -> bool:
    if not isinstance(candidate, dict) or candidate.get("kind") != "card" or candidate.get("enabled") is False:
        return False
    if candidate.get("purpose") != "value_probe":
        return True
    expires = _parse_utc(candidate.get("expires_at"))
    return expires is not None and expires > (now or datetime.now(timezone.utc))


def set_value_probe(card_id: str | None) -> dict:
    cards = load_cards()
    cards_by_id = {c["id"]: c for c in cards}
    if card_id is not None and card_id not in cards_by_id:
        raise ValueError("value probe card is not in the loaded catalog")
    ensure_state()
    now = datetime.now(timezone.utc)
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        existing = state.get("watches", [])
        if not isinstance(existing, list):
            existing = []
        watches = [w for w in existing if not (isinstance(w, dict) and w.get("purpose") == "value_probe")]
        if card_id is not None:
            card = cards_by_id[card_id]
            watches.append({
                "id": f"value-probe-{card_id}",
                "kind": "card",
                "purpose": "value_probe",
                "silent": True,
                "card_id": card_id,
                "label": f"Evaluator price Â· {card.get('name')} {card.get('ovr')}",
                "max_price": None,
                "alert_when_found": False,
                "enabled": True,
                "created_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
            })
        state["watches"] = watches
        write_json_atomic(STATE, state)
    return {
        "schema": VALUE_PROBE_SCHEMA,
        "ok": True,
        "card_id": card_id,
        "active": card_id is not None,
    }


def start_value_probe_batch(card_ids: list[str]) -> dict:
    global VALUE_PROBE_LAST_STATUS
    cards = load_cards()
    cards_by_id = {c["id"]: c for c in cards}
    clean_ids: list[str] = []
    seen: set[str] = set()
    for raw in card_ids:
        card_id = str(raw or "").strip()
        if not card_id or card_id in seen:
            continue
        card = cards_by_id.get(card_id)
        if not card or not normalize_source_url(card.get("source", "")):
            continue
        clean_ids.append(card_id)
        seen.add(card_id)
    if not clean_ids:
        raise ValueError("value probe batch has no valid cards with exact source pages")
    if len(clean_ids) > 40:
        raise ValueError("value probe batch exceeds 40 cards")
    ensure_state()
    now = datetime.now(timezone.utc)
    now_text = now.isoformat().replace("+00:00", "Z")
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        rate_limit = _active_value_probe_rate_limit(state)
        if rate_limit:
            VALUE_PROBE_LAST_STATUS = {
                "status": "RATE_LIMITED",
                "rate_limited": True,
                "completed": int(rate_limit.get("completed") or 0),
                "total": int(rate_limit.get("total") or 0),
                "current_card_id": rate_limit.get("current_card_id"),
                "current_name": rate_limit.get("current_name"),
                "current_ovr": rate_limit.get("current_ovr"),
                "source_url": rate_limit.get("source_url"),
                "observed_at": rate_limit.get("observed_at"),
                "persistent_lock": True,
            }
            raise RuntimeError("market source rate limited; clear the persisted source lock before starting another bulk refresh")
        existing = state.get("watches", [])
        if not isinstance(existing, list):
            existing = []
        watches = [w for w in existing if not (isinstance(w, dict) and w.get("purpose") == "value_probe")]
        first = cards_by_id[clean_ids[0]]
        watch = {
            "id": f"value-probe-batch-{int(now.timestamp())}",
            "kind": "card",
            "purpose": "value_probe",
            "silent": True,
            "card_id": clean_ids[0],
            "label": f"Evaluator price Â· {first.get('name')} {first.get('ovr')}",
            "max_price": None,
            "alert_when_found": False,
            "enabled": True,
            "created_at": now_text,
            "expires_at": (now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
            "batch_card_ids": clean_ids,
            "batch_index": 0,
            "batch_total": len(clean_ids),
            "batch_started_at": now_text,
            "batch_current_started_at": now_text,
            "batch_last_progress_at": now_text,
        }
        watches.append(watch)
        state["watches"] = watches[-50:]
        _set_probe_status_in_state(
            state, "RUNNING", completed=0, total=len(clean_ids),
            current_card_id=clean_ids[0], current_name=first.get("name"), current_ovr=first.get("ovr"),
            current_started_at=now_text, timeout_seconds=VALUE_PROBE_CARD_TIMEOUT_SECONDS,
        )
        write_json_atomic(STATE, state)
    return {
        "schema": VALUE_PROBE_SCHEMA,
        "ok": True,
        "status": "RUNNING",
        "active": True,
        "completed": 0,
        "total": len(clean_ids),
        "current_card_id": clean_ids[0],
        "current_source_url": first["source"],
        "current_started_at": now_text,
        "timeout_seconds": VALUE_PROBE_CARD_TIMEOUT_SECONDS,
    }


def _terminalize_value_probe(status: str, reason: str, source_url: str | None = None, persistent_rate_limit: bool = False) -> dict:
    cards = load_cards()
    cards_by_id = {c["id"]: c for c in cards}
    ensure_state()
    completed = 0
    total = 0
    current_id = None
    current_started_at = None
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        existing = state.get("watches", []) if isinstance(state.get("watches"), list) else []
        kept = []
        for watch in existing:
            if isinstance(watch, dict) and watch.get("purpose") == "value_probe":
                completed = max(completed, int(watch.get("batch_index") or 0))
                total = max(total, int(watch.get("batch_total") or 1))
                current_id = str(watch.get("card_id") or "") or current_id
                current_started_at = watch.get("batch_current_started_at") or watch.get("batch_last_progress_at") or watch.get("batch_started_at") or watch.get("created_at")
                continue
            kept.append(watch)
        state["watches"] = kept
        previous = _probe_status_from_state(state)
        if isinstance(previous, dict):
            completed = max(completed, int(previous.get("completed") or 0))
            total = max(total, int(previous.get("total") or 0))
            current_id = current_id or (str(previous.get("current_card_id") or "") or None)
            current_started_at = current_started_at or previous.get("current_started_at")
        card = cards_by_id.get(current_id or "", {})
        observed_at = _value_probe_now()
        if persistent_rate_limit:
            state[VALUE_PROBE_RATE_LIMIT_KEY] = {
                "active": True,
                "http_status": 429,
                "completed": completed,
                "total": total,
                "current_card_id": current_id,
                "current_name": card.get("name"),
                "current_ovr": card.get("ovr"),
                "source_url": normalize_source_url(source_url or "") or None,
                "observed_at": observed_at,
            }
        payload = _set_probe_status_in_state(
            state, status, completed=completed, total=total, current_card_id=current_id,
            current_name=card.get("name"), current_ovr=card.get("ovr"),
            current_started_at=current_started_at, source_url=normalize_source_url(source_url or "") or None,
            reason=reason, persistent_lock=bool(persistent_rate_limit),
        )
        write_json_atomic(STATE, state)
    record_event(OPERATION_LOG, "value_probe_terminal", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "status": status, "completed": completed, "total": total, "current_card_id": current_id,
        "reason": reason, "persistent_lock": bool(persistent_rate_limit),
    })
    return {
        "schema": VALUE_PROBE_SCHEMA, "ok": True, "active": False,
        "done": status == "COMPLETED", "rate_limited": status == "RATE_LIMITED", **payload,
    }


def stop_value_probe_rate_limited(source_url: str | None = None) -> dict:
    return _terminalize_value_probe(
        "RATE_LIMITED",
        "CFB.FAN returned HTTP 429; bulk refresh stopped and existing prices were preserved.",
        source_url=source_url,
        persistent_rate_limit=True,
    )


def stop_value_probe_source_unavailable(reason: str, source_url: str | None = None) -> dict:
    return _terminalize_value_probe("SOURCE_UNAVAILABLE", reason, source_url=source_url)


def stop_value_probe_timed_out(reason: str, source_url: str | None = None) -> dict:
    return _terminalize_value_probe("TIMED_OUT", reason, source_url=source_url)


def _probe_watch(state: dict) -> dict | None:
    for watch in state.get("watches", []):
        if isinstance(watch, dict) and watch.get("purpose") == "value_probe" and watch.get("enabled") is not False:
            return watch
    return None


def value_probe_status() -> dict:
    cards = load_cards()
    cards_by_id = {c["id"]: c for c in cards}
    ensure_state()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
    rate_limit = _active_value_probe_rate_limit(state)
    if rate_limit:
        return {
            "schema": VALUE_PROBE_SCHEMA, "ok": True, "active": False, "done": False,
            "status": "RATE_LIMITED", "rate_limited": True, "persistent_lock": True,
            "completed": int(rate_limit.get("completed") or 0),
            "total": int(rate_limit.get("total") or 0),
            "current_card_id": rate_limit.get("current_card_id"),
            "current_name": rate_limit.get("current_name"),
            "current_ovr": rate_limit.get("current_ovr"),
            "source_url": rate_limit.get("source_url"),
            "observed_at": rate_limit.get("observed_at"),
        }

    watch = _probe_watch(state)
    if watch:
        batch = watch.get("batch_card_ids") if isinstance(watch.get("batch_card_ids"), list) else None
        index = int(watch.get("batch_index") or 0)
        total = int(watch.get("batch_total") or (len(batch) if batch else 1))
        current_id = str(watch.get("card_id") or "")
        card = cards_by_id.get(current_id, {})
        started_text = watch.get("batch_current_started_at") or watch.get("batch_last_progress_at") or watch.get("batch_started_at") or watch.get("created_at")
        started = _parse_utc(started_text)
        now = datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - started).total_seconds()) if started else None
        expired = _parse_utc(watch.get("expires_at"))
        stale = (age_seconds is not None and age_seconds > VALUE_PROBE_CARD_TIMEOUT_SECONDS) or (expired is not None and expired <= now)
        if stale:
            helper = browser_helper_status()
            diagnostic = helper.get("page_diagnostic") if isinstance(helper, dict) else None
            diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
            diag_stage = str(diagnostic.get("stage") or "")
            diag_url = normalize_source_url(diagnostic.get("url") or "")
            card_url = normalize_source_url(card.get("source", ""))
            same_card_diag = bool(diag_url and card_url and diag_url == card_url)
            if same_card_diag and diag_stage == "market-rate-limited":
                return stop_value_probe_rate_limited(card_url)
            if same_card_diag and diag_stage == "market-source-error":
                return stop_value_probe_source_unavailable(
                    str(diagnostic.get("detail") or "Current market source became unavailable."), card_url
                )
            detail = str(diagnostic.get("detail") or "") if same_card_diag else ""
            reason = "Browser helper did not return a qualifying FOUND/NO_LISTING observation within the bounded card window."
            if detail:
                reason += f" Last page diagnostic: {detail}"
            return stop_value_probe_timed_out(reason, card_url)
        return {
            "schema": VALUE_PROBE_SCHEMA, "ok": True, "status": "RUNNING", "active": True,
            "completed": max(0, index), "total": total, "current_card_id": current_id or None,
            "current_name": card.get("name"), "current_ovr": card.get("ovr"),
            "current_program": card.get("program"), "source_url": _browser_work_url(card.get("source", "")),
            "current_started_at": started_text, "current_age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
            "timeout_seconds": VALUE_PROBE_CARD_TIMEOUT_SECONDS,
        }

    persisted = _probe_status_from_state(state)
    if persisted and persisted.get("status") == "RUNNING":
        return _terminalize_value_probe(
            "INTERRUPTED",
            "A previously running value refresh had no active temporary probe after restart/recovery; it was closed cleanly.",
        )
    if persisted and persisted.get("status") in VALUE_PROBE_TERMINAL_STATUSES:
        status = str(persisted.get("status"))
        return {
            "schema": VALUE_PROBE_SCHEMA, "ok": True, "active": False,
            "done": status == "COMPLETED", "rate_limited": status == "RATE_LIMITED", **persisted,
        }
    return {"schema": VALUE_PROBE_SCHEMA, "ok": True, "status": "IDLE", "active": False, "completed": 0, "total": 0, "done": True}


def advance_value_probe_after_observation(state: dict, observed_card_id: str, cards_by_id: dict[str, dict]) -> dict | None:
    watches = state.get("watches", []) if isinstance(state.get("watches"), list) else []
    for idx, watch in enumerate(watches):
        if not isinstance(watch, dict) or watch.get("purpose") != "value_probe" or watch.get("card_id") != observed_card_id:
            continue
        batch = watch.get("batch_card_ids") if isinstance(watch.get("batch_card_ids"), list) else None
        now_text = _value_probe_now()
        if not batch:
            state["watches"] = watches[:idx] + watches[idx + 1:]
            _set_probe_status_in_state(state, "COMPLETED", completed=1, total=1, current_card_id=observed_card_id)
            return {"status": "COMPLETED", "active": False, "done": True, "completed": 1, "total": 1, "next_card_id": None, "next_source_url": None}
        current_index = int(watch.get("batch_index") or 0)
        next_index = current_index + 1
        total = int(watch.get("batch_total") or len(batch))
        if next_index >= len(batch):
            state["watches"] = watches[:idx] + watches[idx + 1:]
            _set_probe_status_in_state(state, "COMPLETED", completed=min(next_index, total), total=total, current_card_id=observed_card_id)
            return {"status": "COMPLETED", "active": False, "done": True, "completed": min(next_index, total), "total": total, "next_card_id": None, "next_source_url": None}
        next_id = str(batch[next_index])
        next_card = cards_by_id.get(next_id)
        if not next_card or not normalize_source_url(next_card.get("source", "")):
            updated = dict(watch)
            updated["batch_index"] = next_index
            updated["card_id"] = next_id
            updated["batch_last_progress_at"] = now_text
            updated["batch_current_started_at"] = now_text
            watches[idx] = updated
            state["watches"] = watches
            return advance_value_probe_after_observation(state, next_id, cards_by_id)
        updated = dict(watch)
        updated["batch_index"] = next_index
        updated["card_id"] = next_id
        updated["label"] = f"Evaluator price Â· {next_card.get('name')} {next_card.get('ovr')}"
        updated["expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
        updated["batch_last_progress_at"] = now_text
        updated["batch_current_started_at"] = now_text
        watches[idx] = updated
        state["watches"] = watches
        _set_probe_status_in_state(
            state, "RUNNING", completed=next_index, total=total, current_card_id=next_id,
            current_name=next_card.get("name"), current_ovr=next_card.get("ovr"),
            current_started_at=now_text, timeout_seconds=VALUE_PROBE_CARD_TIMEOUT_SECONDS,
        )
        return {
            "status": "RUNNING", "active": True, "done": False, "completed": next_index, "total": total,
            "next_card_id": next_id, "next_source_url": next_card["source"],
            "current_started_at": now_text, "timeout_seconds": VALUE_PROBE_CARD_TIMEOUT_SECONDS,
        }
    return None


def _browser_saved_card_watches(state: dict) -> list[dict]:
    watches = state.get("watches", []) if isinstance(state.get("watches"), list) else []
    return [
        watch for watch in watches
        if isinstance(watch, dict)
        and watch.get("kind") == "card"
        and watch.get("enabled") is not False
        and watch.get("purpose") != "value_probe"
        and watch.get("card_id")
    ]


def _latest_browser_watch_observed_at(state: dict, card_id: str) -> datetime | None:
    latest = None
    rows = state.get("observations", []) if isinstance(state.get("observations"), list) else []
    for raw in rows:
        if not isinstance(raw, dict) or str(raw.get("card_id") or "") != card_id:
            continue
        if raw.get("collection_method") != "USER_STARTED_BROWSER_WATCH":
            continue
        stamp = _parse_utc(raw.get("observed_at"))
        if stamp is not None and (latest is None or stamp > latest):
            latest = stamp
    return latest


def _browser_work_url(source: str) -> str:
    base = normalize_source_url(source)
    return f"{base}{BROWSER_WORK_TAB_FRAGMENT}" if base else ""


def _browser_watch_next_from_state(
    state: dict,
    cards_by_id: dict[str, dict],
    *,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    if _probe_watch(state):
        return {
            "schema": BROWSER_WORK_QUEUE_SCHEMA,
            "ok": True,
            "active": False,
            "status": "VALUE_PROBE_ACTIVE",
            "due_now": False,
            "wait_seconds": None,
            "card_id": None,
            "source_url": None,
        }

    candidates = []
    for watch in _browser_saved_card_watches(state):
        card_id = str(watch.get("card_id") or "")
        card = cards_by_id.get(card_id)
        source_url = _browser_work_url(card.get("source", "") if card else "")
        if not card or not source_url:
            continue
        latest = _latest_browser_watch_observed_at(state, card_id)
        due_at = current if latest is None else latest + timedelta(seconds=BROWSER_WATCH_INTERVAL_SECONDS)
        candidates.append((due_at, card_id, card, watch, source_url))

    if not candidates:
        return {
            "schema": BROWSER_WORK_QUEUE_SCHEMA,
            "ok": True,
            "active": False,
            "status": "IDLE",
            "due_now": False,
            "wait_seconds": None,
            "card_id": None,
            "source_url": None,
        }

    candidates.sort(key=lambda item: (item[0], item[1]))
    due_at, card_id, card, watch, source_url = candidates[0]
    wait_seconds = max(0.0, (due_at - current).total_seconds())
    return {
        "schema": BROWSER_WORK_QUEUE_SCHEMA,
        "ok": True,
        "active": True,
        "status": "DUE" if wait_seconds <= 0.25 else "WAITING",
        "due_now": wait_seconds <= 0.25,
        "wait_seconds": round(wait_seconds, 3),
        "next_due_at": due_at.isoformat().replace("+00:00", "Z"),
        "card_id": card_id,
        "name": card.get("name"),
        "ovr": card.get("ovr"),
        "program": card.get("program"),
        "watch_id": watch.get("id"),
        "source_url": source_url,
        "total_active_card_watches": len(candidates),
    }


def browser_watch_next() -> dict:
    cards = load_cards()
    cards_by_id = {card["id"]: card for card in cards}
    ensure_state()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        return _browser_watch_next_from_state(state, cards_by_id)


def browser_watch_config(page_url: str) -> dict:
    cards = load_cards()
    card = card_for_source_url(page_url, cards)
    ensure_state()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
    watch = None
    if card:
        matches = [
            candidate for candidate in state.get("watches", [])
            if _watch_is_active(candidate) and candidate.get("card_id") == card["id"]
        ]
        probe = next((item for item in matches if item.get("purpose") == "value_probe"), None)
        if probe is not None:
            watch = probe
        elif (
            BROWSER_WORK_TAB_FRAGMENT in str(page_url or "")
            or urlsplit(str(page_url or "")).fragment.lower() == "prices"
        ):
            # The shared work tab begins with #simple-evaluator-worktab, but
            # CFB.FAN replaces the fragment with #prices when its player-local
            # Prices view is selected. Preserve the user-started saved watch on
            # that same exact-card page so a refresh can still record FOUND or
            # NO_LISTING instead of silently deactivating the helper.
            watch = next((item for item in matches if item.get("purpose") != "value_probe"), None)
    return {
        "schema": BROWSER_CONFIG_SCHEMA,
        "active": bool(card and watch),
        "interval_seconds": BROWSER_WATCH_INTERVAL_SECONDS,
        "card_id": card.get("id") if card else None,
        "name": card.get("name") if card else None,
        "ovr": card.get("ovr") if card else None,
        "program": card.get("program") if card else None,
        "watch_id": watch.get("id") if watch else None,
        "watch_purpose": watch.get("purpose") if watch else None,
        "shared_work_tab": bool(watch and watch.get("purpose") != "value_probe"),
    }


def _write_browser_feed(observation: dict, card_ids: set[str]) -> None:
    ensure_feed()
    try:
        existing = read_json(FEED, DEFAULT_FEED).get("observations", [])
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []
    merged = merge_observations(existing, [observation], card_ids)[-100:]
    write_json_atomic(FEED, {
        "source_status": "CONNECTED",
        "source": "USER_STARTED_BROWSER_WATCH",
        "checked_at": observation["observed_at"],
        "observations": merged,
    })


def record_browser_observation(payload: dict, native_alerts: bool = True) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("browser observation must be an object")
    page_url = normalize_source_url(payload.get("source_url", ""))
    if not page_url:
        raise ValueError("browser observation source must be an https://cfb.fan/ page")
    cards = load_cards()
    card = card_for_source_url(page_url, cards)
    if not card:
        raise ValueError("browser page does not match an exact card in the loaded catalog")
    cards_by_id = {c["id"]: c for c in cards}
    card_ids = set(cards_by_id)
    status = str(payload.get("status", "")).upper()
    if status not in {"FOUND", "NO_LISTING"}:
        raise ValueError("browser observation status must be FOUND or NO_LISTING")
    observation = {
        "card_id": card["id"],
        "platform": "PS5",
        "listing_type": "BUY_NOW",
        "status": status,
        "observed_at": payload.get("observed_at"),
        "source": card["source"],
        "listing_count": 0 if status == "NO_LISTING" else payload.get("listing_count"),
        "collection_method": "USER_STARTED_BROWSER_WATCH",
        "browser_family": str(payload.get("browser_family") or "").strip().lower()[:20] or None,
        "helper_version": str(payload.get("helper_version") or "").strip()[:40] or None,
        "release": RELEASE_ID,
        "release_version": RELEASE_VERSION,
    }
    if status == "FOUND":
        observation["price"] = payload.get("price")
        other = payload.get("other_buy_now_prices")
        if isinstance(other, list):
            clean_other = [int(v) for v in other if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
            observation["other_buy_now_prices"] = clean_other[:25]
    else:
        observation["price"] = None

    payload_doc = {"source_status": "CONNECTED", "observations": [observation]}
    ensure_state(); ensure_alerts()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        if not any(_watch_is_active(w) and w.get("card_id") == card["id"] for w in state.get("watches", [])):
            raise ValueError("exact card does not have an active saved watch or value-price probe")
        alerts_doc = read_json(ALERTS, DEFAULT_ALERTS)
        protected_state = {key: state[key] for key in (VALUE_PROBE_RATE_LIMIT_KEY, VALUE_PROBE_STATUS_KEY) if key in state}
        state, alerts_doc, alerts_added = process_payload(
            payload_doc,
            cards_by_id,
            state,
            alerts_doc,
            native_alerts=native_alerts,
        )
        state.update(protected_state)
        value_probe = advance_value_probe_after_observation(state, card["id"], cards_by_id)
        browser_cycle = None
        if not (isinstance(value_probe, dict) and value_probe.get("active") is True):
            browser_cycle = _browser_watch_next_from_state(state, cards_by_id)
        write_json_atomic(STATE, state)
        write_json_atomic(ALERTS, alerts_doc)
    _write_browser_feed(observation, card_ids)
    acceptance = maybe_write_production_acceptance(state)
    record_event(OPERATION_LOG, "browser_observation", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "card_id": card["id"], "status": status, "price": observation.get("price"),
        "listing_count": observation.get("listing_count"), "observed_at": observation.get("observed_at"),
        "browser_family": observation.get("browser_family"), "helper_version": observation.get("helper_version"),
        "alerts_added": alerts_added,
    })
    return {
        "schema": BROWSER_OBSERVATION_SCHEMA,
        "ok": True,
        "card_id": card["id"],
        "status": status,
        "price": observation.get("price"),
        "listing_count": observation.get("listing_count"),
        "observed_at": observation["observed_at"],
        "alerts_added": alerts_added,
        "stored_observations": len(state.get("observations", [])),
        "interval_seconds": BROWSER_WATCH_INTERVAL_SECONDS,
        "browser_family": observation.get("browser_family"),
        "helper_version": observation.get("helper_version"),
        "production_acceptance": acceptance,
        "value_probe": value_probe,
        "browser_cycle": browser_cycle,
    }


def _production_acceptance_candidate(state: dict | None = None) -> dict | None:
    helper = browser_helper_status()
    if not (helper.get("alive") and helper.get("version_matches") and helper.get("browser_family") in {"edge", "chrome"}):
        return None
    expected_version = str(helper.get("expected_version") or "")
    if state is None:
        ensure_state()
        with exclusive_file_lock(STATE_LOCK):
            state = read_json(STATE, DEFAULT_STATE)
    enabled = {
        str(w.get("card_id"))
        for w in state.get("watches", [])
        if isinstance(w, dict) and w.get("kind") == "card" and w.get("enabled") is not False and w.get("card_id")
    }
    grouped: dict[str, list[tuple[datetime, dict]]] = {}
    for obs in state.get("observations", []):
        if not isinstance(obs, dict):
            continue
        card_id = str(obs.get("card_id") or "")
        if card_id not in enabled:
            continue
        if obs.get("collection_method") != "USER_STARTED_BROWSER_WATCH":
            continue
        if obs.get("browser_family") not in {"edge", "chrome"}:
            continue
        if expected_version and obs.get("helper_version") != expected_version:
            continue
        if obs.get("release") != RELEASE_ID or str(obs.get("release_version") or "") != RELEASE_VERSION:
            continue
        stamp = _parse_utc(obs.get("observed_at"))
        if stamp is not None:
            grouped.setdefault(card_id, []).append((stamp, obs))
    for card_id, rows in grouped.items():
        rows.sort(key=lambda item: item[0])
        for i in range(len(rows) - 1, 0, -1):
            second_t, second = rows[i]
            first_t, first = rows[i - 1]
            delta = (second_t - first_t).total_seconds()
            if delta < BROWSER_WATCH_INTERVAL_SECONDS:
                continue
            return {
                "schema": PRODUCTION_ACCEPTANCE_SCHEMA,
                "checkpoint": RELEASE_ID,
                "release_version": RELEASE_VERSION,
                "release_status_before_acceptance": RELEASE_STATUS,
                "status": "PASS",
                "accepted_at": _utc_now(),
                "browser_family": helper.get("browser_family"),
                "browser_helper_version": expected_version or helper.get("reported_version"),
                "card_id": card_id,
                "interval_seconds_required": BROWSER_WATCH_INTERVAL_SECONDS,
                "observed_delta_seconds": round(delta, 3),
                "first_observation": first,
                "second_observation": second,
                "persisted_observations": len(state.get("observations", [])),
            }
    return None


def maybe_write_production_acceptance(state: dict | None = None) -> dict | None:
    # Full 1.4.14 single-worktab acceptance is transactional and is written only
    # by the brokered physical-acceptance action after cadence, tab hygiene,
    # protected-state, stop-condition, evaluator, and restart checks all pass.
    existing = production_acceptance_status()
    if (
        existing.get("status") == "PASS"
        and existing.get("checkpoint") == RELEASE_ID
        and str(existing.get("release_version") or "") == RELEASE_VERSION
        and existing.get("full_single_worktab_acceptance") is True
    ):
        return existing
    return None


def health_payload() -> dict:
    ensure_state(); ensure_alerts()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        alerts_doc = read_json(ALERTS, DEFAULT_ALERTS)
    watches = [w for w in state.get("watches", []) if isinstance(w, dict) and w.get("purpose") != "value_probe"]
    active = [w for w in watches if w.get("enabled") is not False]
    return {
        "schema": "simple-evaluator-health-v1",
        "ok": True,
        "release": RELEASE_ID,
        "release_version": RELEASE_VERSION,
        "release_status": RELEASE_STATUS,
        "browser_watch_interval_seconds": BROWSER_WATCH_INTERVAL_SECONDS,
        "observations": len(state.get("observations", [])),
        "watches": len(watches),
        "active_watches": len(active),
        "paused_watches": len(watches) - len(active),
        "alerts": len(alerts_doc.get("alerts", [])) if isinstance(alerts_doc.get("alerts"), list) else 0,
    }


def write_state(payload: dict) -> None:
    if payload.get("schema") != "simple-evaluator-server-state-v1":
        raise ValueError("unsupported state schema")
    if not isinstance(payload.get("observations"), list) or not isinstance(payload.get("watches"), list):
        raise ValueError("observations and watches must be arrays")
    clean = {
        "schema": "simple-evaluator-server-state-v1",
        "updated_at": payload.get("updated_at"),
        "observations": payload["observations"][-1000:],
        "watches": payload["watches"][-50:],
    }
    with exclusive_file_lock(STATE_LOCK):
        existing = read_json(STATE, DEFAULT_STATE)
        for key in (VALUE_PROBE_RATE_LIMIT_KEY, VALUE_PROBE_STATUS_KEY):
            if key in existing:
                clean[key] = existing[key]
        write_json_atomic(STATE, clean)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def browser_helper_manifest() -> dict:
    path = BROWSER_HELPER / "manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def record_browser_helper_heartbeat(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != BROWSER_HEARTBEAT_SCHEMA:
        raise ValueError("unsupported browser helper heartbeat schema")
    version = str(payload.get("version") or "").strip()[:40]
    if not version:
        raise ValueError("browser helper version is required")
    expected = str(browser_helper_manifest().get("version") or "")
    now = _utc_now()
    browser_family = str(payload.get("browser_family") or "").strip().lower()[:20]
    if browser_family not in {"edge", "chrome", "opera", "chromium"}:
        browser_family = "unknown"
    user_agent = str(payload.get("user_agent") or "").strip()[:240]
    raw_page_diagnostic = payload.get("page_diagnostic")
    page_diagnostic = None
    if isinstance(raw_page_diagnostic, dict):
        page_diagnostic = {
            "stage": str(raw_page_diagnostic.get("stage") or "")[:80] or None,
            "url": str(raw_page_diagnostic.get("url") or "")[:500] or None,
            "observed_at": str(raw_page_diagnostic.get("observed_at") or "")[:80] or None,
            "detail": str(raw_page_diagnostic.get("detail") or "")[:500] or None,
            "price_label_count": raw_page_diagnostic.get("price_label_count"),
            "overview_label_count": raw_page_diagnostic.get("overview_label_count"),
            "peer_label_count": raw_page_diagnostic.get("peer_label_count"),
            "selected": raw_page_diagnostic.get("selected") if isinstance(raw_page_diagnostic.get("selected"), dict) else None,
            "market_state": str(raw_page_diagnostic.get("market_state") or "")[:40] or None,
            "price": raw_page_diagnostic.get("price"),
            "listing_count": raw_page_diagnostic.get("listing_count"),
            "next_refresh_at": str(raw_page_diagnostic.get("next_refresh_at") or "")[:80] or None,
        }
    record = {
        "schema": BROWSER_HEARTBEAT_SCHEMA,
        "version": version,
        "expected_version": expected or None,
        "version_matches": bool(expected and version == expected),
        "browser_family": browser_family,
        "user_agent": user_agent or None,
        "page_diagnostic": page_diagnostic,
        "last_seen_at": now,
        "release": RELEASE_ID,
        "release_version": RELEASE_VERSION,
    }
    # Multiple Chromium profiles may still have an older helper runtime loaded.
    # Once the expected helper has produced a live heartbeat, a mismatched older
    # runtime must not clobber that compatible health record.
    current = {}
    if BROWSER_HEARTBEAT.exists():
        try:
            raw_current = json.loads(BROWSER_HEARTBEAT.read_text(encoding="utf-8"))
            if isinstance(raw_current, dict) and raw_current.get("schema") == BROWSER_HEARTBEAT_SCHEMA:
                current = raw_current
        except (OSError, ValueError, json.JSONDecodeError):
            current = {}
    current_seen = _parse_utc(current.get("last_seen_at")) if current else None
    current_age = None if current_seen is None else max(
        0, int((datetime.now(timezone.utc) - current_seen).total_seconds())
    )
    keep_compatible = bool(
        expected
        and version != expected
        and current.get("version") == expected
        and current_age is not None
        and current_age <= BROWSER_HEARTBEAT_MAX_AGE_SECONDS
    )
    if keep_compatible:
        record_event(OPERATION_LOG, "browser_helper_stale_heartbeat_ignored", release=RELEASE_ID, version=RELEASE_VERSION, details={
            "browser_family": browser_family, "reported_version": version, "expected_version": expected,
            "kept_browser_family": current.get("browser_family"), "kept_version": current.get("version"),
        })
        return {"ok": True, "ignored_version_mismatch": True, **current}
    write_json_atomic(BROWSER_HEARTBEAT, record, backup_existing=False)
    record_event(OPERATION_LOG, "browser_helper_heartbeat", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "browser_family": browser_family, "reported_version": version, "expected_version": expected,
        "version_matches": bool(expected and version == expected),
    })
    return {"ok": True, **record}


def browser_helper_status() -> dict:
    manifest = browser_helper_manifest()
    manifest_present = bool(manifest)
    expected = str(manifest.get("version") or "") if manifest_present else ""
    heartbeat = {}
    if BROWSER_HEARTBEAT.exists():
        try:
            raw = json.loads(BROWSER_HEARTBEAT.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("schema") == BROWSER_HEARTBEAT_SCHEMA:
                heartbeat = raw
        except (OSError, ValueError, json.JSONDecodeError):
            heartbeat = {}
    seen = _parse_utc(heartbeat.get("last_seen_at")) if heartbeat else None
    age = None
    if seen is not None:
        age = max(0, int((datetime.now(timezone.utc) - seen).total_seconds()))
    version = str(heartbeat.get("version") or "")
    return {
        "manifest_present": manifest_present,
        "expected_version": expected or None,
        "heartbeat_present": bool(heartbeat),
        "last_seen_at": heartbeat.get("last_seen_at") if heartbeat else None,
        "age_seconds": age,
        "alive": bool(age is not None and age <= BROWSER_HEARTBEAT_MAX_AGE_SECONDS),
        "reported_version": version or None,
        "version_matches": bool(expected and version and expected == version),
        "browser_family": heartbeat.get("browser_family") if heartbeat else None,
        "user_agent": heartbeat.get("user_agent") if heartbeat else None,
        "page_diagnostic": heartbeat.get("page_diagnostic") if heartbeat else None,
    }


def _valid_object(path: Path, expected_schema: str | None = None) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict):
        return False
    return expected_schema is None or value.get("schema") == expected_schema


def _file_diagnostic(path: Path, fallback: dict, expected_schema: str | None = None) -> dict:
    existed = path.exists()
    valid_before = _valid_object(path, expected_schema) if existed else False
    prior = backup_path(path)
    backup_valid = prior.exists() and _valid_object(prior, expected_schema)
    recovered = False
    if existed and not valid_before and backup_valid:
        read_json(path, fallback)
        recovered = _valid_object(path, expected_schema)
    valid_now = _valid_object(path, expected_schema) if path.exists() else False
    return {
        "file": path.name,
        "exists": path.exists(),
        "valid": valid_now,
        "backup_available": bool(backup_valid),
        "recovered_from_backup": bool(recovered),
    }


def production_acceptance_status() -> dict:
    base = {
        "schema": PRODUCTION_ACCEPTANCE_SCHEMA,
        "checkpoint": RELEASE_ID,
        "release_version": RELEASE_VERSION,
        "status": "PENDING",
        "acceptance_file": PRODUCTION_ACCEPTANCE.name,
    }
    if not PRODUCTION_ACCEPTANCE.exists():
        return base
    try:
        raw = json.loads(PRODUCTION_ACCEPTANCE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {**base, "status": "INVALID", "error": "acceptance record is unreadable"}
    if not isinstance(raw, dict) or raw.get("schema") != PRODUCTION_ACCEPTANCE_SCHEMA:
        return {**base, "status": "INVALID", "error": "acceptance record schema mismatch"}
    if raw.get("checkpoint") != RELEASE_ID or str(raw.get("release_version") or "") != RELEASE_VERSION:
        return {**base, "status": "STALE", "record": raw}
    return raw



def maintenance_status_payload(*, persist: bool = False) -> dict:
    ensure_feed(); ensure_state(); ensure_alerts()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        alerts = read_json(ALERTS, DEFAULT_ALERTS)
        feed = read_json(FEED, DEFAULT_FEED)
    report = evaluate_stability(
        root=ROOT, release=RELEASE, state=state, alerts=alerts, feed=feed,
        helper=browser_helper_status(),
    )
    if persist:
        write_stability_report(report, latest_path=LATEST_STABILITY, history_path=STABILITY_HISTORY)
        record_event(OPERATION_LOG, "maintenance_stability_check", release=RELEASE_ID, version=RELEASE_VERSION, details={
            "status": report.get("status"),
            "liveness": report.get("liveness", {}).get("status"),
            "observations": report.get("metrics", {}).get("observations"),
            "alerts": report.get("metrics", {}).get("alerts"),
        })
    return report

def diagnostics_payload() -> dict:
    ensure_feed(); ensure_state(); ensure_alerts()
    files = {
        "state": _file_diagnostic(STATE, DEFAULT_STATE, "simple-evaluator-server-state-v1"),
        "alerts": _file_diagnostic(ALERTS, DEFAULT_ALERTS, "simple-evaluator-alert-log-v1"),
        "feed": _file_diagnostic(FEED, DEFAULT_FEED),
        "runtime": _file_diagnostic(RUNTIME, DEFAULT_RUNTIME, "simple-evaluator-watch-runtime-v1") if RUNTIME.exists() else {
            "file": RUNTIME.name, "exists": False, "valid": True, "backup_available": backup_path(RUNTIME).exists(), "recovered_from_backup": False
        },
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = sorted(BACKUP_DIR.glob("snapshot-*.json"))
    helper = browser_helper_status()
    helper_ok = helper.get("manifest_present", False)
    acceptance = production_acceptance_status()
    recent_events = read_recent_jsonl(OPERATION_LOG, 10)
    recent_audits = read_recent_jsonl(AUDIT_HISTORY, 5)
    support_bundles = sorted(SUPPORT_BUNDLE_DIR.glob("Simple-Evaluator-Support-*.zip")) if SUPPORT_BUNDLE_DIR.exists() else []
    maintenance = maintenance_status_payload(persist=False)
    return {
        "schema": DIAGNOSTICS_SCHEMA,
        "ok": all(item.get("valid") for item in files.values()) and helper_ok,
        "checked_at": _utc_now(),
        "release": RELEASE,
        "production_acceptance": acceptance,
        "files": files,
        "browser_helper": helper,
        "deployment_ready": bool(helper_ok and helper.get("alive") and helper.get("version_matches")),
        "snapshot_count": len(snapshots),
        "latest_snapshot": snapshots[-1].name if snapshots else None,
        "maintenance": maintenance,
        "operations": {
            "recent_event_count": len(recent_events),
            "latest_event": recent_events[-1] if recent_events else None,
            "recent_audit_count": len(recent_audits),
            "latest_audit_at": recent_audits[-1].get("audited_at") if recent_audits else None,
            "support_bundle_count": len(support_bundles),
            "latest_support_bundle": support_bundles[-1].name if support_bundles else None,
        },
        "browser_watch_interval_seconds": BROWSER_WATCH_INTERVAL_SECONDS,
    }


def operational_audit_payload() -> dict:
    ensure_feed(); ensure_state(); ensure_alerts()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        alerts = read_json(ALERTS, DEFAULT_ALERTS)
        feed = read_json(FEED, DEFAULT_FEED)
    audit = build_audit(
        release=RELEASE,
        health=health_payload(),
        diagnostics=diagnostics_payload(),
        acceptance=production_acceptance_status(),
        state=state,
        alerts=alerts,
        feed=feed,
        helper=browser_helper_status(),
    )
    write_audit(audit, latest_path=LATEST_AUDIT, history_path=AUDIT_HISTORY)
    record_event(OPERATION_LOG, "operational_audit", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "status": "READY" if audit.get("diagnostics", {}).get("ok") else "ATTENTION",
        "watch_count": audit.get("watch_state", {}).get("watch_count"),
        "observation_count": audit.get("observation_state", {}).get("observation_count"),
    })
    return audit


def create_support_bundle_payload(reason: str = "user requested") -> dict:
    audit = operational_audit_payload()
    result = create_support_bundle(ROOT, audit=audit, output_dir=SUPPORT_BUNDLE_DIR, reason=reason)
    result["download_url"] = f"support-bundles/{result['bundle']}"
    record_event(OPERATION_LOG, "support_bundle_created", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "bundle": result.get("bundle"), "sha256": result.get("sha256"), "size": result.get("size"),
    })
    return result


def operational_backup_payload() -> dict:
    ensure_feed(); ensure_state(); ensure_alerts()
    with exclusive_file_lock(STATE_LOCK):
        state = read_json(STATE, DEFAULT_STATE)
        alerts = read_json(ALERTS, DEFAULT_ALERTS)
        feed = read_json(FEED, DEFAULT_FEED)
        runtime = read_json(RUNTIME, DEFAULT_RUNTIME) if RUNTIME.exists() else dict(DEFAULT_RUNTIME)
    return {
        "schema": OPERATIONAL_BACKUP_SCHEMA,
        "created_at": _utc_now(),
        "state": state,
        "alerts": alerts,
        "feed": feed,
        "runtime": runtime,
    }


def _validate_operational_backup(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != OPERATIONAL_BACKUP_SCHEMA:
        raise ValueError("unsupported operational backup schema")
    state = payload.get("state")
    alerts = payload.get("alerts")
    feed = payload.get("feed")
    runtime = payload.get("runtime")
    if not isinstance(state, dict) or state.get("schema") != "simple-evaluator-server-state-v1":
        raise ValueError("backup state is invalid")
    if not isinstance(state.get("observations"), list) or not isinstance(state.get("watches"), list):
        raise ValueError("backup state arrays are invalid")
    if not isinstance(alerts, dict) or alerts.get("schema") != "simple-evaluator-alert-log-v1" or not isinstance(alerts.get("alerts"), list):
        raise ValueError("backup alert log is invalid")
    if not isinstance(feed, dict) or not isinstance(feed.get("observations", []), list):
        raise ValueError("backup feed is invalid")
    if not isinstance(runtime, dict) or runtime.get("schema") != "simple-evaluator-watch-runtime-v1":
        raise ValueError("backup runtime is invalid")
    return {
        "state": {**state, "observations": state["observations"][-1000:], "watches": state["watches"][-50:]},
        "alerts": {**alerts, "alerts": alerts["alerts"][-500:]},
        "feed": {**feed, "observations": feed.get("observations", [])[-100:]},
        "runtime": runtime,
    }


def create_operational_snapshot(reason: str = "manual") -> dict:
    payload = operational_backup_payload()
    payload["reason"] = str(reason)[:80]
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"].replace(":", "").replace("-", "").replace(".", "")
    target = BACKUP_DIR / f"snapshot-{stamp}.json"
    write_json_atomic(target, payload, backup_existing=False)
    snapshots = sorted(BACKUP_DIR.glob("snapshot-*.json"))
    for stale in snapshots[:-20]:
        stale.unlink(missing_ok=True)
    result = {"ok": True, "snapshot": target.name, "created_at": payload["created_at"], "retained": min(20, len(snapshots))}
    record_event(OPERATION_LOG, "operational_snapshot_created", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "snapshot": target.name, "reason": payload.get("reason"), "retained": result["retained"],
    })
    return result


def restore_operational_backup(payload: dict) -> dict:
    clean = _validate_operational_backup(payload)
    safety = create_operational_snapshot("pre-restore safety snapshot")
    with exclusive_file_lock(STATE_LOCK):
        write_json_atomic(STATE, clean["state"])
        write_json_atomic(ALERTS, clean["alerts"])
        write_json_atomic(FEED, clean["feed"])
        write_json_atomic(RUNTIME, clean["runtime"])
    result = {
        "ok": True,
        "restored_at": _utc_now(),
        "safety_snapshot": safety["snapshot"],
        "watches": len(clean["state"].get("watches", [])),
        "observations": len(clean["state"].get("observations", [])),
        "alerts": len(clean["alerts"].get("alerts", [])),
    }
    record_event(OPERATION_LOG, "operational_restore", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "safety_snapshot": result.get("safety_snapshot"), "watches": result.get("watches"),
        "observations": result.get("observations"), "alerts": result.get("alerts"),
    })
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path in {"/", "/Simple-Evaluator.html"}:
            try:
                body = rendered_app_html()
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/catalog-status.json":
            try:
                self._json(200, catalog_status_payload())
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._json(500, {"schema": "simple-evaluator-catalog-status-v1", "status": "ERROR", "error": str(exc)})
            return
        if parsed.path == "/health.json":
            self._json(200, health_payload())
            return
        if parsed.path == "/diagnostics.json":
            self._json(200, diagnostics_payload())
            return
        if parsed.path == "/operational-backup.json":
            self._json(200, operational_backup_payload())
            return
        if parsed.path == "/browser-helper-status.json":
            self._json(200, {"schema": BROWSER_HEARTBEAT_SCHEMA, **browser_helper_status()})
            return
        if parsed.path == "/production-acceptance.json":
            self._json(200, production_acceptance_status())
            return
        if parsed.path == "/latest-operational-audit.json":
            if not LATEST_AUDIT.exists():
                self._json(200, {"schema": AUDIT_SCHEMA, "status": "NOT_RUN"})
                return
            try:
                raw = json.loads(LATEST_AUDIT.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                self._json(500, {"schema": AUDIT_SCHEMA, "status": "INVALID"})
                return
            self._json(200, raw if isinstance(raw, dict) else {"schema": AUDIT_SCHEMA, "status": "INVALID"})
            return
        if parsed.path == "/operational-history.json":
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            except ValueError:
                limit = 50
            limit = max(1, min(200, limit))
            self._json(200, {
                "schema": "simple-evaluator-operational-history-v1",
                "events": read_recent_jsonl(OPERATION_LOG, limit),
                "audits": read_recent_jsonl(AUDIT_HISTORY, min(limit, 50)),
            })
            return
        if parsed.path == "/maintenance-status.json":
            self._json(200, maintenance_status_payload(persist=False))
            return
        if parsed.path == "/app-state.json":
            ensure_state()
            body = STATE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/browser-watch-config.json":
            try:
                page_url = parse_qs(parsed.query).get("url", [""])[0]
                self._json(200, browser_watch_config(page_url))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"schema": BROWSER_CONFIG_SCHEMA, "active": False, "error": str(exc)})
            return
        if parsed.path == "/browser-watch-next.json":
            self._json(200, browser_watch_next())
            return
        if parsed.path == "/value-probe-status.json":
            try:
                self._json(200, value_probe_status())
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "error": str(exc)})
            return
        if parsed.path == "/browser-watch-cycle-start":
            result = browser_watch_next()
            target = str(result.get("source_url") or "")
            if not result.get("active") or not target:
                self._json(409, {"schema": BROWSER_WORK_QUEUE_SCHEMA, "ok": False, "error": "no active exact-card browser watch"})
                return
            self.send_response(302)
            self.send_header("Location", BROWSER_NORMAL_SEARCH_URL)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path == "/value-probe-start":
            try:
                raw = parse_qs(parsed.query).get("cards", [""])[0]
                card_ids = [item.strip() for item in raw.split(",") if item.strip()]
                result = start_value_probe_batch(card_ids)
                target = str(result.get("current_source_url") or "")
                if not normalize_source_url(target):
                    raise ValueError("first value probe card has no valid source URL")
            except RuntimeError as exc:
                self._json(429, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "status": "RATE_LIMITED", "rate_limited": True, "persistent_lock": True, "error": str(exc)})
                return
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(400, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "error": str(exc)})
                return
            self.send_response(302)
            self.send_header("Location", BROWSER_NORMAL_SEARCH_URL)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        if parsed.path == "/authorized-market-refresh":
            try:
                result = authorized_market_refresh()
            except PermissionError as exc:
                self._json(409, {
                    "schema": "simple-evaluator-authorized-market-refresh-v1",
                    "ok": False,
                    "status": "MARKET_SOURCE_UNAVAILABLE",
                    "authorization_required": True,
                    "error": str(exc),
                })
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(409, {
                    "schema": "simple-evaluator-authorized-market-refresh-v1",
                    "ok": False,
                    "status": "MARKET_SOURCE_UNAVAILABLE",
                    "authorization_required": True,
                    "error": str(exc),
                })
                return
            except (OSError, RuntimeError, URLError, HTTPError) as exc:
                self._json(502, {
                    "schema": "simple-evaluator-authorized-market-refresh-v1",
                    "ok": False,
                    "status": "MARKET_SOURCE_UNAVAILABLE",
                    "authorization_required": False,
                    "error": str(exc),
                })
                return
            self._json(200, result)
            return

        if parsed.path == "/update-catalog":
            try:
                force = parse_qs(parsed.query).get("force", ["0"])[0].lower() in {"1", "true", "yes"}
                trigger = "manual button" if force else "daily app check"
                result = refresh_catalog(force=force, trigger=trigger)
            except CatalogSourceRequired as exc:
                self._json(409, {"schema": "simple-evaluator-catalog-refresh-v1", "ok": False, "needs_source": True, "error": str(exc), "status": catalog_status_payload()})
                return
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"schema": "simple-evaluator-catalog-refresh-v1", "ok": False, "error": str(exc), "status": catalog_status_payload()})
                return
            self._json(200, result)
            return

        if parsed.path == "/import-catalog":
            try:
                if length <= 0 or length > MAX_CATALOG_FEED_BYTES:
                    raise ValueError("invalid catalog feed size")
                payload = json.loads(self.rfile.read(length))
                result = apply_catalog_feed(payload, trigger="browser file import")
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(400, {"schema": "simple-evaluator-catalog-refresh-v1", "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/browser-helper-heartbeat":
            try:
                if length <= 0 or length > MAX_BROWSER_HEARTBEAT_BYTES:
                    raise ValueError("invalid browser helper heartbeat size")
                payload = json.loads(self.rfile.read(length))
                result = record_browser_helper_heartbeat(payload)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(400, {"schema": BROWSER_HEARTBEAT_SCHEMA, "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/run-maintenance-check":
            try:
                result = maintenance_status_payload(persist=True)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"schema": STABILITY_SCHEMA, "status": "ATTENTION", "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/create-backup":
            try:
                result = create_operational_snapshot("user requested")
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/run-operational-audit":
            try:
                result = operational_audit_payload()
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"schema": AUDIT_SCHEMA, "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/create-support-bundle":
            try:
                result = create_support_bundle_payload("user requested")
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/restore-backup":
            try:
                if length <= 0 or length > MAX_OPERATIONAL_BACKUP_BYTES:
                    raise ValueError("invalid operational backup size")
                payload = json.loads(self.rfile.read(length))
                result = restore_operational_backup(payload)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/value-probe-clear-rate-limit":
            try:
                self._json(200, clear_value_probe_rate_limit())
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._json(500, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "error": str(exc)})
            return

        if parsed.path == "/value-probe-rate-limited":
            try:
                if length <= 0 or length > 10_000:
                    raise ValueError("invalid rate-limit payload size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("rate-limit payload must be an object")
                result = stop_value_probe_rate_limited(str(payload.get("source_url") or ""))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/value-probe":
            try:
                if length <= 0 or length > 10_000:
                    raise ValueError("invalid value probe payload size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("value probe payload must be an object")
                raw_card_id = payload.get("card_id")
                card_id = str(raw_card_id).strip() if raw_card_id not in {None, ""} else None
                result = set_value_probe(card_id)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"schema": VALUE_PROBE_SCHEMA, "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        if parsed.path == "/app-state.json":
            try:
                if length <= 0 or length > MAX_STATE_BYTES:
                    raise ValueError("invalid state size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("state must be an object")
                write_state(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            self._json(200, {"ok": True})
            return

        if parsed.path == "/browser-observation":
            try:
                if length <= 0 or length > MAX_BROWSER_OBSERVATION_BYTES:
                    raise ValueError("invalid browser observation size")
                payload = json.loads(self.rfile.read(length))
                result = record_browser_observation(payload, native_alerts=True)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"schema": BROWSER_OBSERVATION_SCHEMA, "ok": False, "error": str(exc)})
                return
            self._json(200, result)
            return

        self.send_error(404)


def browser_candidates(name: str) -> list[Path]:
    key = name.lower()
    names = {
        "edge": ["msedge", "microsoft-edge"],
        "chrome": ["chrome", "google-chrome", "google-chrome-stable"],
        "opera": ["opera", "opera.exe"],
    }
    candidates: list[Path] = []
    for cmd in names.get(key, []):
        found = shutil.which(cmd)
        if found:
            candidates.append(Path(found))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    pf = Path(os.environ.get("PROGRAMFILES", ""))
    pfx = Path(os.environ.get("PROGRAMFILES(X86)", ""))
    if key == "edge":
        candidates += [pf / "Microsoft/Edge/Application/msedge.exe", pfx / "Microsoft/Edge/Application/msedge.exe"]
    elif key == "chrome":
        candidates += [pf / "Google/Chrome/Application/chrome.exe", pfx / "Google/Chrome/Application/chrome.exe", local / "Google/Chrome/Application/chrome.exe"]
    elif key == "opera":
        candidates += [local / "Programs/Opera/opera.exe", local / "Programs/Opera GX/opera.exe"]
    return [c for c in candidates if str(c) and c.exists()]


def open_browser(url: str, name: str = "default", isolated_profile: bool = False) -> str:
    if name == "none":
        return "not opened"
    if name == "auto":
        for preferred in ("edge", "chrome"):
            if browser_candidates(preferred):
                return open_browser(url, preferred, isolated_profile=isolated_profile)
        webbrowser.open(url)
        return "default browser (Edge/Chrome not found)"
    if name == "default":
        webbrowser.open(url)
        return "default browser"
    choices = browser_candidates(name)
    if choices:
        cmd = [str(choices[0])]
        if name in {"edge", "chrome", "opera"}:
            if isolated_profile:
                profile = BROWSER_PROFILE_ROOT / name
                profile.mkdir(parents=True, exist_ok=True)
                cmd += [f"--user-data-dir={profile}", "--no-first-run"]
            if BROWSER_HELPER.exists():
                cmd += [f"--load-extension={BROWSER_HELPER}"]
        cmd.append(url)
        subprocess.Popen(cmd)
        return str(choices[0])
    webbrowser.open(url)
    return f"default browser (requested {name} not found)"


def startup_urls(app_url: str, login_first: bool = True) -> list[str]:
    return [CFB_LOGIN_URL, app_url] if login_first else [app_url]


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    ensure_feed(); ensure_state(); ensure_alerts()
    # Recover abandoned temporary value-refresh state before serving the UI.
    # This never converts a source failure into NO_LISTING; it only closes stale probe state.
    try:
        value_probe_status()
    except Exception as exc:
        record_event(OPERATION_LOG, "value_probe_startup_recovery_error", release=RELEASE_ID, version=RELEASE_VERSION, details={"error": str(exc)})
    if port == 0:
        return ExclusiveThreadingHTTPServer((host, 0), Handler)
    last_error: OSError | None = None
    for candidate in range(port, port + 10):
        try:
            return ExclusiveThreadingHTTPServer((host, candidate), Handler)
        except OSError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Simple Evaluator locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--browser", choices=["auto", "default", "edge", "chrome", "opera", "none"], default="auto")
    parser.add_argument("--isolated-browser-profile", action="store_true", help="use a separate app-managed browser profile; intended only for explicit testing/isolation")
    parser.add_argument("--skip-login-first", action="store_true", help="skip the normal CFB.FAN-first startup step; intended for offline/test use")
    args = parser.parse_args()
    server = make_server(args.host, args.port)
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}/Simple-Evaluator.html"
    print(f"Simple Evaluator: {url}", flush=True)
    record_event(OPERATION_LOG, "server_start", release=RELEASE_ID, version=RELEASE_VERSION, details={
        "host": args.host, "port": actual_port, "browser": "none" if args.no_browser else args.browser,
    })
    browser_name = "none" if args.no_browser else args.browser
    if browser_name == "none":
        print("Browser: not opened", flush=True)
    else:
        for index, startup_url in enumerate(startup_urls(url, login_first=not args.skip_login_first), start=1):
            opened = open_browser(startup_url, browser_name, isolated_profile=args.isolated_browser_profile)
            label = "CFB.FAN login/session" if startup_url == CFB_LOGIN_URL else "Simple Evaluator"
            print(f"Browser step {index} ({label}): {opened} -> {startup_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        record_event(OPERATION_LOG, "server_stop", release=RELEASE_ID, version=RELEASE_VERSION, details={"port": actual_port})
        server.server_close()


if __name__ == "__main__":
    main()
