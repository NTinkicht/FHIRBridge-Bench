"""All-attempt developer accounting (synthetic fixtures only)."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from fhirbridge.path_b_outcome_audit import audit_path_b_all_attempts


def _fixture():
    manifest, observations = [], []
    for model in ("M-A", "M-B"):
        for arm in ("direct", "repair"):
            for case in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
                core = {
                    "source_instance_id": case,
                    "model_key": model,
                    "strategy": arm,
                    "analysis_cluster_id": "cluster-" + case,
                }
                states = {
                    "direct": [
                        "VALID_G1_FAITHFUL",
                        "VALID_G1_UNFAITHFUL",
                        "INVALID_G0",
                        "INVALID_G1",
                        "VALID_G1_SEMANTIC_INDETERMINATE",
                        "STRUCTURAL_MEASUREMENT_FAILURE",
                        "STRUCTURAL_POLICY_UNRESOLVED",
                    ],
                    "repair": [
                        "INVALID_G0",
                        "VALID_G1_FAITHFUL",
                        "VALID_G1_FAITHFUL",
                        "VALID_G1_UNFAITHFUL",
                        "STRUCTURAL_POLICY_UNRESOLVED",
                        "STRUCTURAL_MEASUREMENT_FAILURE",
                        "INVALID_G1",
                    ],
                }
                state = states[arm][int(case[1:]) - 1]
                manifest.append(core)
                observations.append(core | {"outcome": state})
    return manifest, observations


def _audit():
    return audit_path_b_all_attempts(*_fixture())


def test_complete_all_attempt_census_counts_every_partition_state() -> None:
    report = _audit()
    assert report.status == "PREFREEZE_SYNTHETIC_ANALYSIS_ONLY"
    assert report.expected_assignment_count == 28
    assert report.accounted_assignment_count == 28
    assert len(report.arm_censuses) == 4
    assert len(report.paired_vfy_censuses) == 2

    direct = next(
        arm for arm in report.arm_censuses
        if arm.model_key == "M-A" and arm.strategy == "direct"
    )
    repair = next(
        arm for arm in report.arm_censuses
        if arm.model_key == "M-A" and arm.strategy == "repair"
    )
    assert direct.all_attempts == repair.all_attempts == 7
    assert dict(direct.counts_by_state) == {
        "INVALID_G0": 1,
        "INVALID_G1": 1,
        "VALID_G1_FAITHFUL": 1,
        "VALID_G1_UNFAITHFUL": 1,
        "VALID_G1_SEMANTIC_INDETERMINATE": 1,
        "STRUCTURAL_MEASUREMENT_FAILURE": 1,
        "STRUCTURAL_POLICY_UNRESOLVED": 1,
    }
    assert direct.vfy_g1_all_attempts == 1 / 7
    assert direct.valid_unfaithful_yield_g1_all_attempts == 1 / 7
    assert direct.descriptive_vur_g1 == 0.5
    assert repair.vfy_g1_all_attempts == 2 / 7
    assert repair.valid_unfaithful_yield_g1_all_attempts == 1 / 7
    assert repair.descriptive_vur_g1 == 1 / 3
    pair = next(x for x in report.paired_vfy_censuses if x.model_key == "M-A")
    assert pair.all_paired_assignments == 7
    assert (pair.both_vfy, pair.a_only_vfy, pair.b_only_vfy, pair.neither_vfy) == (
        0, 1, 2, 4,
    )
    assert report.approved_confirmatory_estimand is False
    assert report.G1_qualified is False
    assert report.confirmatory_permission is False


def test_missing_outcome_fails_instead_of_shrinking_denominator() -> None:
    manifest, rows = _fixture()
    rows.pop()
    with pytest.raises(ValueError, match="1 prospectively expected"):
        audit_path_b_all_attempts(manifest, rows)


def test_duplicate_observation_fails_instead_of_double_counting() -> None:
    manifest, rows = _fixture()
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError, match="duplicate observed"):
        audit_path_b_all_attempts(manifest, rows)


def test_unplanned_observation_fails_instead_of_inflating_denominator() -> None:
    manifest, rows = _fixture()
    extra = deepcopy(rows[0])
    extra["source_instance_id"] = "FORGED-CASE"
    rows.append(extra)
    with pytest.raises(ValueError, match="unplanned outcome assignment"):
        audit_path_b_all_attempts(manifest, rows)


def test_duplicate_planned_assignment_fails() -> None:
    manifest, rows = _fixture()
    manifest.append(deepcopy(manifest[0]))
    with pytest.raises(ValueError, match="duplicate expected"):
        audit_path_b_all_attempts(manifest, rows)


def test_observed_cluster_cannot_be_recomputed_posthoc() -> None:
    manifest, rows = _fixture()
    rows[0]["analysis_cluster_id"] = "other-cluster"
    with pytest.raises(ValueError, match="observed cluster differs"):
        audit_path_b_all_attempts(manifest, rows)


def test_source_cluster_must_stay_constant_across_models_and_arms() -> None:
    manifest, rows = _fixture()
    manifest[1]["analysis_cluster_id"] = "other-cluster"
    with pytest.raises(ValueError, match="cannot change its analysis cluster"):
        audit_path_b_all_attempts(manifest, rows)


def test_unbalanced_strategy_case_sets_do_not_create_selected_pairs() -> None:
    manifest, rows = _fixture()
    key = {"source_instance_id": "C7", "model_key": "M-A", "strategy": "repair"}
    manifest = [
        row for row in manifest
        if any(row[k] != v for k, v in key.items())
    ]
    rows = [
        row for row in rows
        if any(row[k] != v for k, v in key.items())
    ]
    with pytest.raises(ValueError, match="incomplete crossed design"):
        audit_path_b_all_attempts(manifest, rows)


def test_empty_valid_determinate_denominator_reports_null_conditional_vur() -> None:
    manifest, rows = _fixture()
    rows = [
        row | {"outcome": "STRUCTURAL_POLICY_UNRESOLVED"}
        for row in rows
    ]
    result = audit_path_b_all_attempts(manifest, rows)
    for arm in result.arm_censuses:
        assert arm.descriptive_vur_g1 is None
        assert arm.vfy_g1_all_attempts == 0
        assert arm.valid_unfaithful_yield_g1_all_attempts == 0
    assert all(p.neither_vfy == 7 for p in result.paired_vfy_censuses)


def test_outcome_manifest_bytes_are_separately_accounted_by_hash() -> None:
    manifest, rows = _fixture()
    original = audit_path_b_all_attempts(manifest, rows)
    edited = deepcopy(rows)
    edited[0]["outcome"] = "INVALID_G0"
    modified = audit_path_b_all_attempts(manifest, edited)
    assert original.manifest_sha256 == modified.manifest_sha256
    assert original.observed_sha256 != modified.observed_sha256
    assert len(original.manifest_sha256) == len(sha256(b"test").hexdigest())


@pytest.mark.parametrize(
    "bad", [
        "VALID",
        "UNASSESSED",
        "UNKNOWN",
        "VALID_G1",
        "MEASUREMENT_FAILURE",
        "",
        None,
        False,
        0,
    ]
)
def test_unknown_or_coerced_state_cannot_be_classified(bad) -> None:
    manifest, rows = _fixture()
    rows[0]["outcome"] = bad
    with pytest.raises(ValueError, match="approved candidate partition state|identifiers"):
        audit_path_b_all_attempts(manifest, rows)


@pytest.mark.parametrize("key", [
    "source_instance_id", "model_key", "strategy", "analysis_cluster_id"
])
def test_malformed_identifiers_cannot_be_coerced(key: str) -> None:
    manifest, rows = _fixture()
    rows[0][key] = " C1 " if key == "source_instance_id" else False
    with pytest.raises(ValueError, match="identifiers must be"):
        audit_path_b_all_attempts(manifest, rows)


def test_unexpected_outcome_fields_rejected() -> None:
    manifest, rows = _fixture()
    rows[0]["qualified_G1"] = True
    with pytest.raises(ValueError, match="missing or additional fields"):
        audit_path_b_all_attempts(manifest, rows)


def test_status_and_gate_properties_are_immutable() -> None:
    report = _audit()
    with pytest.raises(FrozenInstanceError):
        report.G1_qualified = True
    with pytest.raises(FrozenInstanceError):
        report.confirmatory_permission = True
    with pytest.raises(FrozenInstanceError):
        report.approved_confirmatory_estimand = True
