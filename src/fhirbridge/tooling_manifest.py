"""Validation helpers for the frozen tooling/terminology manifest.

The manifest intentionally distinguishes candidate pins from a confirmatory
freeze. A study run may not claim frozen dependency provenance while unresolved
values or required false qualification flags remain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FreezeReadiness:
    ready: bool
    manifest_status: str
    unresolved_paths: tuple[str, ...]
    false_boolean_paths: tuple[str, ...]


def _path_value(document: dict[str, Any], dotted_path: str) -> Any:
    value: Any = document
    for component in dotted_path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise ValueError(f"manifest path not found: {dotted_path}")
        value = value[component]
    return value


def assess_freeze_readiness(document: dict[str, Any]) -> FreezeReadiness:
    """Return whether a tooling manifest satisfies its own freeze gate."""

    manifest = document.get("manifest")
    gate = document.get("freeze_gate")
    if not isinstance(manifest, dict):
        raise ValueError("tooling manifest must contain a manifest mapping")
    if not isinstance(gate, dict):
        raise ValueError("tooling manifest must contain a freeze_gate mapping")

    status = manifest.get("status")
    if not isinstance(status, str) or not status:
        raise ValueError("manifest.status must be a non-empty string")

    unresolved_token = gate.get("unresolved_token")
    if not isinstance(unresolved_token, str) or not unresolved_token:
        raise ValueError("freeze_gate.unresolved_token must be a non-empty string")

    required_values = gate.get("required_before_status_frozen")
    required_true = gate.get("required_boolean_true_before_status_frozen")
    if not isinstance(required_values, list) or not all(
        isinstance(path, str) and path for path in required_values
    ):
        raise ValueError("required_before_status_frozen must be a list of paths")
    if not isinstance(required_true, list) or not all(
        isinstance(path, str) and path for path in required_true
    ):
        raise ValueError(
            "required_boolean_true_before_status_frozen must be a list of paths"
        )

    unresolved = tuple(
        path
        for path in required_values
        if _path_value(document, path) in {None, "", unresolved_token}
    )
    false_flags = tuple(
        path
        for path in required_true
        if _path_value(document, path) is not True
    )

    ready = not unresolved and not false_flags
    if status == "frozen" and not ready:
        raise ValueError(
            "manifest cannot be marked frozen while freeze-gate requirements remain"
        )

    return FreezeReadiness(
        ready=ready,
        manifest_status=status,
        unresolved_paths=unresolved,
        false_boolean_paths=false_flags,
    )


def assert_confirmatory_frozen(document: dict[str, Any]) -> None:
    """Reject a dependency manifest that is not ready for confirmatory scoring."""

    readiness = assess_freeze_readiness(document)
    if readiness.manifest_status != "frozen":
        raise ValueError(
            f"tooling manifest status must be frozen, got {readiness.manifest_status!r}"
        )
    if not readiness.ready:
        raise ValueError("tooling manifest freeze gate is incomplete")



def freeze_readiness_to_dict(readiness: FreezeReadiness) -> dict[str, object]:
    """Return a stable machine-readable freeze-readiness record."""

    return {
        "ready": readiness.ready,
        "manifest_status": readiness.manifest_status,
        "unresolved_paths": list(readiness.unresolved_paths),
        "false_boolean_paths": list(readiness.false_boolean_paths),
        "blocker_count": (
            len(readiness.unresolved_paths) + len(readiness.false_boolean_paths)
        ),
    }
