from pathlib import Path

import pytest

from fhirbridge.fhir_warning_audit import (
    audit_warning_logs,
    audit_to_dict,
    load_warning_policy,
)

_POLICY = Path("benchmark/fhir_validator_warning_policy.yaml")


def test_warning_policy_is_unique_and_loadable() -> None:
    categories = load_warning_policy(_POLICY)

    ids = [category_id for category_id, _ in categories]
    assert len(ids) == len(set(ids))
    assert "DOMAIN_RESOURCE_NARRATIVE_BEST_PRACTICE" in ids
    assert "OFFLINE_UCUM_TERMINOLOGY_CHECK" in ids


def test_warning_audit_classifies_known_warning_classes(tmp_path: Path) -> None:
    (tmp_path / "LAB-001.log").write_text(
        "\n".join(
            [
                "Warning @ Bundle.entry[0].resource: Constraint failed: dom-6: narrative",
                "Warning @ Observation: Best Practice Recommendation: In general, all observations should have a performer",
                "Warning @ Observation.value: Unable to validate code 'mg/dL' in system 'http://unitsofmeasure.org' because the validator is running without terminology services",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    audit = audit_warning_logs(tmp_path, _POLICY)

    assert audit.total_warnings == 3
    assert audit.unknown_warnings == 0
    assert audit.category_counts["DOMAIN_RESOURCE_NARRATIVE_BEST_PRACTICE"] == 1
    assert audit.category_counts["OBSERVATION_PERFORMER_BEST_PRACTICE"] == 1
    assert audit.category_counts["OFFLINE_UCUM_TERMINOLOGY_CHECK"] == 1


def test_warning_audit_exposes_unknown_warning_instead_of_ignoring_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "LAB-001.log").write_text(
        "Warning @ Observation: unexpected new structural warning\n",
        encoding="utf-8",
    )

    audit = audit_warning_logs(tmp_path, _POLICY)

    assert audit.total_warnings == 1
    assert audit.unknown_warnings == 1
    assert audit.classifications[0].category_id is None
    assert audit_to_dict(audit)["unknown_warnings"] == 1


def test_warning_audit_rejects_overlapping_categories(tmp_path: Path) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        """
categories:
  - category_id: A
    regex: "Warning"
  - category_id: B
    regex: "performer"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "LAB-001.log").write_text(
        "Warning @ Observation: performer\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="multiple policy categories"):
        audit_warning_logs(tmp_path, policy)
