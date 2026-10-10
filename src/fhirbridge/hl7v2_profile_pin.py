"""Readiness checks for the exact HL7 v2 LRI profile freeze record."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hl7v2_profile_bundle import ProfileBundleManifest, compute_profile_bundle_manifest


@dataclass(frozen=True)
class Hl7ProfilePinReadiness:
    ready: bool
    status: str
    unresolved_paths: tuple[str, ...]
    false_boolean_paths: tuple[str, ...]
    exact_value_mismatches: tuple[str, ...]


def _path_value(document: dict[str, Any], dotted_path: str) -> Any:
    value: Any = document
    for component in dotted_path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise ValueError(f"profile-pin path not found: {dotted_path}")
        value = value[component]
    return value


def assess_hl7_profile_pin(document: dict[str, Any]) -> Hl7ProfilePinReadiness:
    """Check that no stale or ambiguous profile can be marked frozen."""

    header = document.get("profile_pin")
    gate = document.get("freeze_gate")
    if not isinstance(header, dict):
        raise ValueError("profile pin must contain profile_pin metadata")
    if not isinstance(gate, dict):
        raise ValueError("profile pin must contain freeze_gate metadata")

    status = header.get("status")
    if not isinstance(status, str) or not status:
        raise ValueError("profile_pin.status must be a non-empty string")

    unresolved_token = gate.get("unresolved_token")
    if not isinstance(unresolved_token, str) or not unresolved_token:
        raise ValueError("freeze_gate.unresolved_token must be non-empty")

    exact = gate.get("required_exact_values")
    resolved = gate.get("required_resolved_paths")
    required_true = gate.get("required_true_paths")
    if not isinstance(exact, dict):
        raise ValueError("required_exact_values must be a mapping")
    if not isinstance(resolved, list) or not all(
        isinstance(path, str) and path for path in resolved
    ):
        raise ValueError("required_resolved_paths must be a list of paths")
    if not isinstance(required_true, list) or not all(
        isinstance(path, str) and path for path in required_true
    ):
        raise ValueError("required_true_paths must be a list of paths")

    mismatches = tuple(
        path
        for path, expected in exact.items()
        if _path_value(document, path) != expected
    )
    unresolved = tuple(
        path
        for path in resolved
        if _path_value(document, path) in {None, "", unresolved_token}
    )
    false_flags = tuple(
        path for path in required_true if _path_value(document, path) is not True
    )
    ready = not mismatches and not unresolved and not false_flags

    if status == "frozen" and not ready:
        raise ValueError(
            "HL7 profile pin cannot be marked frozen while provenance or "
            "qualification requirements remain"
        )

    return Hl7ProfilePinReadiness(
        ready=ready,
        status=status,
        unresolved_paths=unresolved,
        false_boolean_paths=false_flags,
        exact_value_mismatches=mismatches,
    )


def assert_hl7_profile_pin_frozen(document: dict[str, Any]) -> None:
    """Require a fully qualified and explicitly frozen LRI profile pin."""

    readiness = assess_hl7_profile_pin(document)
    if readiness.status != "frozen":
        raise ValueError(
            f"HL7 profile pin status must be frozen, got {readiness.status!r}"
        )
    if not readiness.ready:
        raise ValueError("HL7 profile pin freeze gate is incomplete")


def assert_profile_bundle_matches_pin(
    root: Path,
    document: dict[str, Any],
) -> ProfileBundleManifest:
    """Require a local bundle to match the cryptographic profile pin.

    This check intentionally runs before validator qualification. A historical
    comparator or vendor-specific profile must not be able to satisfy the
    Edition 5 qualification path merely because it is also HL7 v2.5.1 ORU^R01.
    """

    bundle = document.get("bundle")
    if not isinstance(bundle, dict):
        raise ValueError("profile pin must contain bundle metadata")

    expected_aggregate = bundle.get("aggregate_sha256")
    expected_profile = bundle.get("profile_xml_sha256")
    for field_name, value in (
        ("bundle.aggregate_sha256", expected_aggregate),
        ("bundle.profile_xml_sha256", expected_profile),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in value)
        ):
            raise ValueError(
                f"{field_name} must be a resolved 64-character SHA-256 before "
                "local profile qualification"
            )

    manifest = compute_profile_bundle_manifest(root)
    profile_file = next(
        (item for item in manifest.files if item.name == "PROFILE.xml"),
        None,
    )
    if profile_file is None:  # pragma: no cover - manifest already requires it
        raise ValueError("profile bundle manifest does not contain PROFILE.xml")

    mismatches: list[str] = []
    if manifest.aggregate_sha256.lower() != expected_aggregate.lower():
        mismatches.append("bundle.aggregate_sha256")
    if profile_file.sha256.lower() != expected_profile.lower():
        mismatches.append("bundle.profile_xml_sha256")
    if mismatches:
        raise ValueError(
            "local profile bundle does not match the pinned Edition 5 artifact: "
            + ", ".join(mismatches)
        )
    return manifest
