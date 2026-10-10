import pytest
import yaml

from fhirbridge.lifters.hl7v251_oru import (
    _observation_status,
    _report_status,
)
from fhirbridge.renderers.hl7v251_oru_a import (
    _observation_status_code,
    _report_status_code,
)

_PATH = "benchmark/status_mapping_candidates.yaml"


def _doc() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_primary_report_statuses_have_unique_reverse_candidates() -> None:
    doc = _doc()
    mapping = doc["diagnostic_report_to_obr25"]["safe_unique_inverse"]

    assert mapping["preliminary"] == "P"
    assert mapping["final"] == "F"
    assert mapping["corrected"] == "C"
    assert _report_status_code("preliminary") == "P"
    assert _report_status_code("final") == "F"
    assert _report_status_code("corrected") == "C"


def test_primary_observation_statuses_have_unique_reverse_candidates() -> None:
    doc = _doc()
    mapping = doc["observation_to_obx11"]["safe_unique_inverse"]

    assert mapping["preliminary"] == "P"
    assert mapping["final"] == "F"
    assert mapping["corrected"] == "C"
    assert _observation_status_code("preliminary") == "P"
    assert _observation_status_code("final") == "F"
    assert _observation_status_code("corrected") == "C"


@pytest.mark.parametrize("status", ["registered", "amended", "appended", "entered-in-error", "unknown"])
def test_report_reverse_mapping_fails_closed_when_not_unique(status: str) -> None:
    with pytest.raises(ValueError, match="not uniquely reversible"):
        _report_status_code(status)


@pytest.mark.parametrize("status", ["registered", "partial", "appended", "entered-in-error", "unknown"])
def test_observation_reverse_mapping_fails_closed_when_not_unique(status: str) -> None:
    with pytest.raises(ValueError, match="not uniquely reversible"):
        _observation_status_code(status)


def test_report_lifter_uses_distinct_v2_to_fhir_semantics() -> None:
    assert _report_status("O") == "registered"
    assert _report_status("I") == "registered"
    assert _report_status("S") == "registered"
    assert _report_status("R") == "partial"
    assert _report_status("P") == "preliminary"
    assert _report_status("C") == "corrected"
    assert _report_status("F") == "final"
    assert _report_status("X") == "cancelled"
    assert _report_status("U") is None


def test_observation_lifter_does_not_reuse_report_status_semantics() -> None:
    assert _observation_status("A") == "amended"
    assert _observation_status("C") == "corrected"
    assert _observation_status("D") == "entered-in-error"
    assert _observation_status("F") == "final"
    assert _observation_status("P") == "preliminary"
    assert _observation_status("X") == "cancelled"
    assert _observation_status("W") == "entered-in-error"
    assert _observation_status("R") is None


def test_status_candidate_file_remains_unfrozen_and_requires_independent_review() -> None:
    doc = _doc()

    assert doc["status_mapping_candidates"]["status"] == (
        "draft_external_review_required"
    )
    requirements = set(doc["freeze_requirements"])
    assert "independent_external_review_of_reverse_status_maps" in requirements
    assert "exact_LRI_Edition5_profile_binding_check" in requirements
