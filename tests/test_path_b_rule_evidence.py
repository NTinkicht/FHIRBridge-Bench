"""Developer-only Path B rule evidence cannot mint scientific G1 approval."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from fhirbridge.path_b_rule_evidence import assess_path_b_rule_evidence

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/"
    "path_b_rule_evidence_dev_template.json"
)
_COVERAGE = Path("benchmark/path_b_bounded_coverage.yaml")
_FREEZE = Path("benchmark/protocol_freeze_gates.yaml")


def _inputs() -> tuple[dict, dict, dict]:
    import json

    return (
        json.loads(_TEMPLATE.read_text(encoding="utf-8")),
        yaml.safe_load(_COVERAGE.read_text(encoding="utf-8")),
        yaml.safe_load(_FREEZE.read_text(encoding="utf-8")),
    )


def _check(doc: dict, coverage: dict, freeze: dict):
    return assess_path_b_rule_evidence(
        doc, coverage=coverage, protocol_gates=freeze
    )


def _synthetic_complete_rule(rule: dict) -> dict:
    """Test *shape* only, never represent a real human response."""
    rule = deepcopy(rule)
    rule["usage"] = "R"
    rule["applicability"] = "UNCONDITIONAL"
    rule["disposition"] = "ADJUDICATED"
    rule["source_anchor"] = {
        "guide_pages": [185],
        "errata_review": "NO_APPLICABLE_ERRATA",
        "errata_references": [],
    }
    rule["reader_a"] = {
        "extractor_pseudonym": "TEST-A",
        "response_lock_sha256": "a" * 64,
    }
    rule["reader_b"] = {
        "extractor_pseudonym": "TEST-B",
        "response_lock_sha256": "b" * 64,
    }
    rule["adjudicator"] = {
        "pseudonym": "TEST-ADJ",
        "private_evidence_ref": "TEST-ONLY-PROTECTED-REF",
        "double_omission_audit_ref": "TEST-ONLY-AUDIT-REF",
    }
    rule["positive_control"] = {
        "control_id": "TEST-POS",
        "expected_locus": rule["locus"],
        "observed_locus": rule["locus"],
        "result": "PASS_EXPECTED_LOCUS",
        "evidence_sha256": "c" * 64,
    }
    rule["negative_control"] = {
        "control_id": "TEST-NEG",
        "expected_locus": rule["locus"],
        "observed_locus": rule["locus"],
        "result": "PASS_EXPECTED_LOCUS",
        "evidence_sha256": "d" * 64,
    }
    return rule


def test_real_prefreeze_template_fails_closed_without_human_evidence() -> None:
    doc, coverage, freeze = _inputs()
    result = _check(doc, coverage, freeze)
    assert result.rule_count == 3
    assert result.G1_qualified is False
    assert result.confirmatory_permission is False
    assert result.status == "PREFREEZE_MECHANICAL_EVIDENCE_ONLY"
    assert result.mechanical_record_checks_complete is False
    assert any("denominator is absent" in item for item in result.blockers)
    assert any(
        "PB-MSH21-PROFILE: not independently adjudicated" in item
        for item in result.blockers
    )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("status", "G1_QUALIFIED"),
        ("schema_version", "42"),
        ("rules", []),
        ("fake_signoff", True),
    ],
)
def test_schema_refuses_unsupported_status_or_extra_fields(
    field: str, bad: object,
) -> None:
    doc, coverage, freeze = _inputs()
    doc[field] = bad
    with pytest.raises(ValueError, match="invalid Path B evidence format"):
        _check(doc, coverage, freeze)


def test_duplicate_rule_id_is_reported_as_a_blocker() -> None:
    doc, coverage, freeze = _inputs()
    doc["rules"].append(deepcopy(doc["rules"][0]))
    assert "PB-MSH21-PROFILE: duplicate rule ID" in _check(
        doc, coverage, freeze
    ).blockers


@pytest.mark.parametrize("which", ["register", "coverage", "components"])
def test_source_or_component_substitution_is_rejected(which: str) -> None:
    doc, coverage, freeze = _inputs()
    if which == "register":
        doc["normative_sources"]["guide_sha256"] = "0" * 64
    elif which == "coverage":
        coverage["path_b_bounded_coverage"]["normative_source"][
            "errata_letter_sha256"
        ] = "0" * 64
    else:
        doc["normative_sources"]["components"] = [
            "LRI_Common_Component_V3",
            "LRI_NG_Component_R1",
            "UNREVIEWED_OTHER",
        ]
    with pytest.raises(ValueError, match="format|identity mismatch"):
        _check(doc, coverage, freeze)


@pytest.mark.parametrize(
    ("scope", "field", "value"),
    [
        ("freeze", "status", "frozen"),
        ("decision", "confirmatory_permission", True),
        ("decision", "gated_qualification_alternative_implemented", True),
        ("coverage", "status", "qualified"),
        ("claims", "confirmatory_G1_validity_authorized", True),
    ],
)
def test_changed_scientific_boundary_refuses_a_development_report(
    scope: str, field: str, value: object,
) -> None:
    doc, coverage, freeze = _inputs()
    targets = {
        "freeze": freeze["protocol_freeze"],
        "decision": freeze["protocol_freeze"]["development_path_decision"],
        "coverage": coverage["path_b_bounded_coverage"],
        "claims": coverage["path_b_bounded_coverage"]["claims"],
    }
    targets[scope][field] = value
    with pytest.raises(ValueError, match="prefreeze boundary changed"):
        _check(doc, coverage, freeze)


def test_even_synthetic_complete_rule_cannot_clear_missing_independent_denominator() -> None:
    doc, coverage, freeze = _inputs()
    doc["rules"] = [_synthetic_complete_rule(doc["rules"][0])]
    result = _check(doc, coverage, freeze)
    assert result.G1_qualified is False
    assert result.confirmatory_permission is False
    assert not result.mechanical_record_checks_complete
    assert any("denominator is absent" in item for item in result.blockers)


def test_same_person_as_reader_and_adjudicator_is_rejected() -> None:
    doc, coverage, freeze = _inputs()
    rule = _synthetic_complete_rule(doc["rules"][0])
    rule["adjudicator"]["pseudonym"] = "TEST-A"
    doc["rules"] = [rule]
    assert any("not role-separated" in item for item in _check(
        doc, coverage, freeze
    ).blockers)


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("wrong_locus", "negative control not evidenced at expected locus"),
        ("unrun", "negative control not evidenced at expected locus"),
        ("missing_digest", "negative control not evidenced at expected locus"),
        ("same_id", "positive and negative controls are not distinct"),
    ],
)
def test_controls_need_expected_field_and_independent_evidence(
    variant: str, expected: str,
) -> None:
    doc, coverage, freeze = _inputs()
    rule = _synthetic_complete_rule(doc["rules"][0])
    if variant == "wrong_locus":
        rule["negative_control"]["observed_locus"] = "OBR-3"
    elif variant == "unrun":
        rule["negative_control"]["result"] = "UNRUN"
    elif variant == "missing_digest":
        rule["negative_control"]["evidence_sha256"] = None
    else:
        rule["negative_control"]["control_id"] = "TEST-POS"
    doc["rules"] = [rule]
    assert any(expected in item for item in _check(
        doc, coverage, freeze
    ).blockers)


def test_conditional_rule_without_predicate_is_not_accepted() -> None:
    doc, coverage, freeze = _inputs()
    rule = _synthetic_complete_rule(doc["rules"][0])
    rule["usage"] = "C"
    rule["applicability"] = "CONDITIONAL"
    rule["condition"] = None
    doc["rules"] = [rule]
    assert any("conditional predicate not established" in item for item in _check(
        doc, coverage, freeze
    ).blockers)


def test_missing_guide_evidence_and_unreviewed_errata_never_pass() -> None:
    doc, coverage, freeze = _inputs()
    rule = _synthetic_complete_rule(doc["rules"][0])
    rule["source_anchor"]["guide_pages"] = []
    rule["source_anchor"]["errata_review"] = "UNASSESSED"
    doc["rules"] = [rule]
    report = _check(doc, coverage, freeze)
    assert any("no guide page citations" in item for item in report.blockers)
    assert any("errata applicability unresolved" in item for item in report.blockers)


def test_placeholder_private_review_reference_fails_closed() -> None:
    doc, coverage, freeze = _inputs()
    rule = _synthetic_complete_rule(doc["rules"][0])
    rule["adjudicator"]["private_evidence_ref"] = "TBD"
    doc["rules"] = [rule]
    assert any("original review chain missing" in item for item in _check(
        doc, coverage, freeze
    ).blockers)


def test_exclusion_is_never_a_free_unreviewed_rule_removal() -> None:
    doc, coverage, freeze = _inputs()
    rule = doc["rules"][0]
    rule["disposition"] = "EXCLUDED_WITH_REASON"
    rule["exclusion_reason"] = "TEST-ONLY rationale"
    doc["rules"] = [rule]
    assert any("separately authorized scope review" in item for item in _check(
        doc, coverage, freeze
    ).blockers)
