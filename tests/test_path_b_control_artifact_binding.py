"""Developer-only Path B control binding rejects source/file/approval spoofing."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256

import pytest

from fhirbridge.path_b_control_artifact_binding import (
    ControlConstructionBinding,
    bind_unrun_control_artifacts,
)


def _artifact(*, filler: str = "A", version: str = "2.5.1", pid: str = "P") -> bytes:
    msh = ["MSH"] + [""] * 12
    msh[1] = "^~\\&"
    msh[8] = "ORU^R01^ORU_R01"
    msh[11] = version
    return (
        "|".join(msh) + "\r" +
        "PID|||"+ pid + "\r" +
        "ORC|RE||" + filler + "\r" +
        "OBR|1||ORDER-SOURCE|1234^Test^LN\r"
    ).encode("utf-8")


def _inputs(*, locus: str = "ORC-3") -> tuple[dict, dict, bytes, bytes]:
    positive = _artifact()
    negative = _artifact(filler="B")
    manifest = {
        "schema_version": "0.1.0",
        "status": "PREFREEZE_CONSTRUCTION_ONLY",
        "rule_id": "PB-ORC3-TEST",
        "expected_locus": locus,
        "positive_control_id": "TEST-POS",
        "negative_control_id": "TEST-NEG",
        "positive_artifact_sha256": sha256(positive).hexdigest(),
        "negative_artifact_sha256": sha256(negative).hexdigest(),
    }
    rule = {
        "rule_id": "PB-ORC3-TEST",
        "locus": locus,
        "disposition": "UNASSESSED",
        "positive_control": {
            "control_id": "TEST-POS",
            "expected_locus": locus,
            "observed_locus": None,
            "result": "UNRUN",
            "evidence_sha256": None,
        },
        "negative_control": {
            "control_id": "TEST-NEG",
            "expected_locus": locus,
            "observed_locus": None,
            "result": "UNRUN",
            "evidence_sha256": None,
        },
    }
    return manifest, rule, positive, negative


def _bind(manifest: dict, rule: dict, positive: bytes, negative: bytes):
    return bind_unrun_control_artifacts(
        manifest, rule=rule, positive_bytes=positive, negative_bytes=negative
    )


def test_exact_bytes_and_locus_bind_without_claiming_g1() -> None:
    manifest, rule, positive, negative = _inputs()
    binding = _bind(manifest, rule, positive, negative)
    assert binding.expected_locus == "ORC-3"
    assert binding.rule_id == "PB-ORC3-TEST"
    assert binding.positive_artifact_sha256 == sha256(positive).hexdigest()
    assert binding.negative_artifact_sha256 == sha256(negative).hexdigest()
    assert binding.status == "PREFREEZE_ARTIFACT_BYTES_BOUND_ONLY"
    assert binding.G1_qualified is False
    assert binding.validator_expected_locus_failure_confirmed is False
    assert binding.confirmatory_permission is False


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("positive", "positive artifact digest does not match"),
        ("negative", "negative artifact digest does not match"),
    ],
)
def test_actual_bytes_must_match_manifest_digest(role: str, expected: str) -> None:
    manifest, rule, positive, negative = _inputs()
    manifest[f"{role}_artifact_sha256"] = "f" * 64
    with pytest.raises(ValueError, match=expected):
        _bind(manifest, rule, positive, negative)


def test_same_bytes_cannot_be_negative_control() -> None:
    manifest, rule, positive, _ = _inputs()
    manifest["negative_artifact_sha256"] = manifest["positive_artifact_sha256"]
    with pytest.raises(ValueError, match="must be distinct"):
        _bind(manifest, rule, positive, positive)


@pytest.mark.parametrize(
    ("key", "value", "why"),
    [
        ("status", "QUALIFIED", "development-only"),
        ("schema_version", "1.0.0", "development-only"),
        ("rule_id", "PB-WRONG", "rule identity"),
        ("expected_locus", "OBR-3", "expected locus"),
        ("positive_control_id", "TEST-NEG", "identifiers are missing or not distinct"),
        ("negative_control_id", "TEST-POS", "identifiers are missing or not distinct"),
        ("negative_artifact_sha256", "0" * 64, "invalid SHA-256"),
    ],
)
def test_unsupported_or_inaccurate_manifest_fails(
    key: str, value: str, why: str,
) -> None:
    manifest, rule, positive, negative = _inputs()
    manifest[key] = value
    with pytest.raises(ValueError, match=why):
        _bind(manifest, rule, positive, negative)


def test_extra_field_cannot_supply_fabricated_qualification_status() -> None:
    manifest, rule, positive, negative = _inputs()
    manifest["G1_qualified"] = True
    with pytest.raises(ValueError, match="invalid development control manifest"):
        _bind(manifest, rule, positive, negative)


@pytest.mark.parametrize("field", ["positive_control", "negative_control"])
def test_control_record_must_be_present_and_unrun(field: str) -> None:
    manifest, rule, positive, negative = _inputs()
    rule[field]["result"] = "PASS_EXPECTED_LOCUS"
    with pytest.raises(ValueError, match="unrun, unqualified"):
        _bind(manifest, rule, positive, negative)
    rule[field]["result"] = "UNRUN"
    rule[field]["evidence_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="unrun, unqualified"):
        _bind(manifest, rule, positive, negative)
    rule[field]["evidence_sha256"] = None
    rule[field]["observed_locus"] = "ORC-3"
    with pytest.raises(ValueError, match="unrun, unqualified"):
        _bind(manifest, rule, positive, negative)


def test_absent_control_record_is_rejected() -> None:
    manifest, rule, positive, negative = _inputs()
    rule["negative_control"] = None
    with pytest.raises(ValueError, match="negative control record not present"):
        _bind(manifest, rule, positive, negative)


def test_single_locus_diff_is_not_determined_from_claimed_manifest() -> None:
    manifest, rule, positive, negative = _inputs(locus="OBR-3")
    # All metadata agrees on OBR-3, but the actual only change is ORC-3.
    with pytest.raises(ValueError, match="unexpected mutated locus: ORC-3"):
        _bind(manifest, rule, positive, negative)


def test_two_simultaneous_fields_cannot_be_laundered_as_one_control() -> None:
    manifest, rule, positive, _ = _inputs()
    negative = _artifact(filler="B", pid="OTHER")
    manifest["negative_artifact_sha256"] = sha256(negative).hexdigest()
    with pytest.raises(ValueError, match="exactly one HL7 field must change"):
        _bind(manifest, rule, positive, negative)


def test_invalid_utf8_is_rejected_after_byte_hash_verification() -> None:
    manifest, rule, positive, _ = _inputs()
    negative = b"\xff\xfe\x80"
    manifest["negative_artifact_sha256"] = sha256(negative).hexdigest()
    with pytest.raises(ValueError, match="must be UTF-8"):
        _bind(manifest, rule, positive, negative)


def test_control_pair_does_not_mutate_original_rule_or_manifest() -> None:
    manifest, rule, positive, negative = _inputs()
    manifest_saved = deepcopy(manifest)
    rule_saved = deepcopy(rule)
    _bind(manifest, rule, positive, negative)
    assert manifest == manifest_saved
    assert rule == rule_saved


@pytest.mark.parametrize(
    ("forged", "value"),
    [
        ("G1_qualified", True),
        ("validator_expected_locus_failure_confirmed", True),
        ("confirmatory_permission", True),
        ("status", "G1_QUALIFIED"),
    ],
)
def test_cannot_forge_approval_by_direct_construction_or_replace(
    forged: str, value: object,
) -> None:
    manifest, rule, positive, negative = _inputs()
    binding = _bind(manifest, rule, positive, negative)
    attrs = {
        "rule_id": binding.rule_id,
        "expected_locus": binding.expected_locus,
        "positive_control_id": binding.positive_control_id,
        "negative_control_id": binding.negative_control_id,
        "positive_artifact_sha256": binding.positive_artifact_sha256,
        "negative_artifact_sha256": binding.negative_artifact_sha256,
    }
    with pytest.raises(TypeError):
        ControlConstructionBinding(**(attrs | {forged: value}))
    with pytest.raises(TypeError):
        replace(binding, **{forged: value})
    with pytest.raises(FrozenInstanceError):
        setattr(binding, forged, value)


@pytest.mark.parametrize("role", ["positive", "negative"])
@pytest.mark.parametrize("separator", [b"\n", b"\r\n"])
def test_changed_segment_separator_cannot_pass_as_one_field_edit(
    role: str, separator: bytes,
) -> None:
    manifest, rule, positive, negative = _inputs()
    if role == "positive":
        positive = positive.replace(b"\r", separator)
        manifest["positive_artifact_sha256"] = sha256(positive).hexdigest()
    else:
        negative = negative.replace(b"\r", separator)
        manifest["negative_artifact_sha256"] = sha256(negative).hexdigest()
    with pytest.raises(ValueError, match="CR-only segment delimiters"):
        _bind(manifest, rule, positive, negative)


@pytest.mark.parametrize("role", ["positive", "negative"])
def test_missing_final_cr_cannot_pass_as_one_field_edit(role: str) -> None:
    manifest, rule, positive, negative = _inputs()
    if role == "positive":
        positive = positive.removesuffix(b"\r")
        manifest["positive_artifact_sha256"] = sha256(positive).hexdigest()
    else:
        negative = negative.removesuffix(b"\r")
        manifest["negative_artifact_sha256"] = sha256(negative).hexdigest()
    with pytest.raises(ValueError, match="CR-only segment delimiters"):
        _bind(manifest, rule, positive, negative)
