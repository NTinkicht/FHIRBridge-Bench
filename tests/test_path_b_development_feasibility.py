"""Eleven-family development evidence must never manufacture a G1 pass."""

from pathlib import Path

import pytest
import yaml

import fhirbridge.renderers
from fhirbridge.path_b_development_feasibility import (
    build_development_feasibility,
)

_SCENARIOS = Path("benchmark/scenarios/lab_core_v0.1.yaml")
_FREEZE = Path("benchmark/protocol_freeze_gates.yaml")


def test_eleven_primary_families_are_explicitly_nonqualifying() -> None:
    report = build_development_feasibility()
    assert report["status"] == "PREFREEZE_NOT_SCIENTIFICALLY_QUALIFIED"
    assert report["scientific_role"] == "development_feasibility_only"
    assert report["primary_family_count"] == 11
    assert report["development_fhir_roundtrip_draft_faithful_count"] == 11
    assert report["hl7v2_order_renderer_fail_closed_count"] == 11
    assert report["independent_G1_qualified_family_count"] == 0
    assert report["confirmatory_permission"] is False
    assert report["sealed_set_opened"] is False
    assert report["source_completeness_denominator_established"] is False
    assert list(row["family_id"] for row in report["rows"]) == [
        f"LAB-{index:03d}" for index in range(1, 12)
    ]
    assert len({row["seed"] for row in report["rows"]}) == 11
    for row in report["rows"]:
        assert row["source_order_fact_present"] is True
        assert row["fhir_service_request_and_based_on_present"] is True
        assert row["fhir_development_roundtrip"] == (
            "FAITHFUL_UNDER_DRAFT_POLICY_ONLY"
        )
        assert row["hl7v2_order_context_serialization"] == "BLOCKED_FAIL_CLOSED"
        assert row["hl7v2_edition5_bounded_g1_status"] == "NOT_QUALIFIED"
        assert row["external_fhir_validator_checked_by_this_report"] is False
        assert row["confirmatory_evidence"] is False
    assert all(len(digest) == 64 for digest in report["input_sha256"].values())


def test_report_is_byte_deterministic_without_external_validator() -> None:
    assert build_development_feasibility() == build_development_feasibility()


def test_missing_primary_family_is_not_reported_as_eleven(tmp_path: Path) -> None:
    spec = yaml.safe_load(_SCENARIOS.read_text(encoding="utf-8"))
    spec["scenario_families"][0]["primary_endpoint_eligible"] = False
    changed = tmp_path / "missing-family.yaml"
    changed.write_text(yaml.safe_dump(spec), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly LAB-001 through LAB-011"):
        build_development_feasibility(scenario_path=changed)


def test_unapproved_protocol_change_refuses_development_evidence(
    tmp_path: Path,
) -> None:
    freeze = yaml.safe_load(_FREEZE.read_text(encoding="utf-8"))
    freeze["protocol_freeze"]["development_path_decision"][
        "confirmatory_permission"
    ] = True
    changed = tmp_path / "changed-freeze.yaml"
    changed.write_text(yaml.safe_dump(freeze), encoding="utf-8")
    with pytest.raises(ValueError, match="development-only feasibility runner"):
        build_development_feasibility(freeze_path=changed)


def test_unexpected_hl7_success_is_guard_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fhirbridge.renderers.Hl7V251OruRendererA,
        "render",
        lambda *_args, **_kwargs: object(),
    )
    with pytest.raises(ValueError, match="unexpectedly bypassed its G1 guard"):
        build_development_feasibility()


def test_unexpected_hl7_error_cannot_be_misreported_as_expected_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise ValueError("unrelated renderer failure")

    monkeypatch.setattr(
        fhirbridge.renderers.Hl7V251OruRendererA,
        "render",
        broken,
    )
    with pytest.raises(ValueError, match="unexpected HL7 rendering error"):
        build_development_feasibility()
