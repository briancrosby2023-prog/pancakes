"""Fail-closed tool broker for consequential Operation Pancake execution."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class ToolExecutionBlocked(RuntimeError):
    pass


class DecisionAuthorizer(Protocol):
    def authorize_action(
        self,
        decision_id: str,
        action: str,
        *,
        current_state_snapshot: Any = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    mutating: bool
    handler: Callable[..., Any]


class ControlledToolBroker:
    """Expose read tools freely but require a valid SOP decision for mutations.

    The intended integration is that the model sees only broker-backed tools.
    Mutation handlers are never exposed directly to the model/runtime.
    """

    def __init__(self, authorizer: DecisionAuthorizer):
        self.authorizer = authorizer
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        *,
        mutating: bool,
        handler: Callable[..., Any],
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("tool name is required")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = ToolSpec(name, mutating, handler)

    def allowed_tool_names(
        self,
        *,
        preflight_passed: bool,
        granted_actions: Sequence[str] = (),
    ) -> tuple[str, ...]:
        granted = {str(item).strip() for item in granted_actions if str(item).strip()}
        names = []
        for name, spec in self._tools.items():
            if not spec.mutating:
                names.append(name)
            elif preflight_passed and name in granted:
                names.append(name)
        return tuple(sorted(names))

    def responses_allowed_tools(
        self,
        *,
        preflight_passed: bool,
        granted_actions: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Build the Responses API allowed_tools restriction for registered functions."""
        names = self.allowed_tool_names(
            preflight_passed=preflight_passed,
            granted_actions=granted_actions,
        )
        return {
            "type": "allowed_tools",
            "mode": "auto",
            "tools": [{"type": "function", "name": name} for name in names],
        }

    def call(
        self,
        name: str,
        *,
        kwargs: Mapping[str, Any] | None = None,
        decision_id: str | None = None,
        current_state_snapshot: Any = None,
    ) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolExecutionBlocked(f"tool is not registered: {name}")
        if spec.mutating:
            if not decision_id:
                raise ToolExecutionBlocked(
                    f"mutation tool {name} requires a decision_id"
                )
            if current_state_snapshot is None:
                raise ToolExecutionBlocked(
                    f"mutation tool {name} requires current project state"
                )
            try:
                self.authorizer.authorize_action(
                    decision_id,
                    name,
                    current_state_snapshot=current_state_snapshot,
                )
            except Exception as exc:
                raise ToolExecutionBlocked(str(exc)) from exc
        return spec.handler(**dict(kwargs or {}))
