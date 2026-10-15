"""Bind *synthetic control-construction* claims to exact artifact bytes.

This function verifies a development manifest against a rule register and the
actual bytes of its source and single-field negative artifacts. It does NOT
interpret Edition 5, attest reviewers, validate a positive, observe a
validator rejection, or qualify G1. Only pre-verdict UNRUN controls are allowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .path_b_surgical_mutation import audit_single_field_mutation

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_RULE_ID = re.compile(r"^PB-[A-Z0-9-]+$")


@dataclass(frozen=True)
class ControlConstructionBinding:
    rule_id: str
    expected_locus: str
    positive_control_id: str
    negative_control_id: str
    positive_artifact_sha256: str
    negative_artifact_sha256: str

    @property
    def status(self) -> str:
        return "PREFREEZE_ARTIFACT_BYTES_BOUND_ONLY"

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def validator_expected_locus_failure_confirmed(self) -> bool:
        return False

    @property
    def confirmatory_permission(self) -> bool:
        return False


_REQUIRED_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "rule_id",
        "expected_locus",
        "positive_control_id",
        "negative_control_id",
        "positive_artifact_sha256",
        "negative_artifact_sha256",
    }
)


def _digest_is_valid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and _SHA256.fullmatch(value) is not None
        and set(value) != {"0"}
    )


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def bind_unrun_control_artifacts(
    manifest: dict[str, Any],
    *,
    rule: dict[str, Any],
    positive_bytes: bytes,
    negative_bytes: bytes,
) -> ControlConstructionBinding:
    """Reject misbound control IDs, files, hashes and field-locus mutations.

    The caller is responsible for authenticating file custody; passing this
    check certifies only the stated mechanical construction properties.
    """
    if not isinstance(manifest, dict) or set(manifest) != _REQUIRED_MANIFEST_FIELDS:
        raise ValueError("invalid development control manifest fields")
    if (
        manifest["schema_version"] != "0.1.0"
        or manifest["status"] != "PREFREEZE_CONSTRUCTION_ONLY"
    ):
        raise ValueError("manifest must remain development-only")
    if not isinstance(rule, dict):
        raise ValueError("rule record is missing")
    if (
        not _nonblank(manifest["rule_id"])
        or _RULE_ID.fullmatch(manifest["rule_id"]) is None
        or rule.get("rule_id") != manifest["rule_id"]
        or rule.get("locus") != manifest["expected_locus"]
    ):
        raise ValueError("control manifest rule identity or expected locus mismatch")
    if (
        not _nonblank(manifest["positive_control_id"])
        or not _nonblank(manifest["negative_control_id"])
        or manifest["positive_control_id"] == manifest["negative_control_id"]
    ):
        raise ValueError("control identifiers are missing or not distinct")

    for role in ("positive", "negative"):
        record = rule.get(f"{role}_control")
        if not isinstance(record, dict):
            raise ValueError(f"{role} control record not present")
        if (
            record.get("control_id") != manifest[f"{role}_control_id"]
            or record.get("expected_locus") != manifest["expected_locus"]
            or record.get("result") != "UNRUN"
            or record.get("observed_locus") is not None
            or record.get("evidence_sha256") is not None
        ):
            raise ValueError(
                f"{role} control must be a matching, unrun, unqualified record"
            )

    if not isinstance(positive_bytes, bytes) or not isinstance(negative_bytes, bytes):
        raise ValueError("both control artifacts must be byte strings")
    for role, contents in (
        ("positive", positive_bytes),
        ("negative", negative_bytes),
    ):
        expected = manifest[f"{role}_artifact_sha256"]
        if not _digest_is_valid(expected):
            raise ValueError(f"{role} artifact has invalid SHA-256 claim")
        actual = sha256(contents).hexdigest()
        if actual != expected:
            raise ValueError(f"{role} artifact digest does not match supplied bytes")
    if manifest["positive_artifact_sha256"] == manifest["negative_artifact_sha256"]:
        raise ValueError("positive and negative artifacts must be distinct")

    try:
        positive_text = positive_bytes.decode("utf-8", errors="strict")
        negative_text = negative_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("control artifact bytes must be UTF-8") from exc

    observed = audit_single_field_mutation(
        positive_text, negative_text, expected_locus=manifest["expected_locus"]
    )
    if (
        observed.before_sha256 != manifest["positive_artifact_sha256"]
        or observed.after_sha256 != manifest["negative_artifact_sha256"]
    ):
        raise ValueError("surgical mutation proof is not bound to the original bytes")

    return ControlConstructionBinding(
        rule_id=manifest["rule_id"],
        expected_locus=manifest["expected_locus"],
        positive_control_id=manifest["positive_control_id"],
        negative_control_id=manifest["negative_control_id"],
        positive_artifact_sha256=manifest["positive_artifact_sha256"],
        negative_artifact_sha256=manifest["negative_artifact_sha256"],
    )
