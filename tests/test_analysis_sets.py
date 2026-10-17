import pytest

from fhirbridge.analysis_sets import (
    build_paired_vfy_set,
    build_paired_vur_set,
)


def _rows() -> list[dict]:
    return [
        {
            "case_id": "C1",
            "cluster_id": "P1",
            "arms": {
                "A": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "UNFAITHFUL",
                },
                "B": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "FAITHFUL",
                },
            },
        },
        {
            "case_id": "C2",
            "cluster_id": "P1",
            "arms": {
                "A": {
                    "structural_outcome": "INVALID",
                    "semantic_verdict": "FAITHFUL",
                },
                "B": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "FAITHFUL",
                },
            },
        },
        {
            "case_id": "C3",
            "cluster_id": "P2",
            "arms": {
                "A": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "INDETERMINATE",
                },
                "B": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "UNFAITHFUL",
                },
            },
        },
        {
            "case_id": "C4",
            "cluster_id": "P3",
            "arms": {
                "A": {
                    "structural_outcome": "VALID",
                    "semantic_verdict": "FAITHFUL",
                },
                "B": {
                    "structural_outcome": "MEASUREMENT_FAILURE",
                    "semantic_verdict": "INDETERMINATE",
                },
            },
        },
    ]


def test_paired_vur_set_uses_only_both_valid_determinate_cases() -> None:
    result = build_paired_vur_set(_rows(), arm_a="A", arm_b="B")

    assert result.estimand == "VUR"
    assert result.case_ids == ("C1",)
    assert result.cluster_ids == ("P1",)
    assert result.outcome_a == (1,)
    assert result.outcome_b == (0,)
    assert result.excluded_case_count == 3
    assert result.exclusion_counts == {
        "arm_a_invalid": 1,
        "arm_a_semantic_indeterminate": 1,
        "arm_b_measurement_failure": 1,
    }


def test_paired_vfy_set_keeps_every_explicit_attempt() -> None:
    result = build_paired_vfy_set(_rows(), arm_a="A", arm_b="B")

    assert result.estimand == "VFY"
    assert result.case_ids == ("C1", "C2", "C3", "C4")
    assert result.cluster_ids == ("P1", "P1", "P2", "P3")
    assert result.outcome_a == (0, 0, 0, 1)
    assert result.outcome_b == (1, 1, 0, 0)
    assert result.excluded_case_count == 0
    assert result.exclusion_counts == {}


def test_missing_arm_attempt_is_error_not_silent_exclusion() -> None:
    rows = _rows()
    del rows[0]["arms"]["B"]

    with pytest.raises(ValueError, match="missing explicit attempted-transform"):
        build_paired_vur_set(rows, arm_a="A", arm_b="B")


def test_duplicate_case_id_is_rejected() -> None:
    rows = _rows()
    rows.append(rows[0])

    with pytest.raises(ValueError, match="duplicate analysis case_id"):
        build_paired_vfy_set(rows, arm_a="A", arm_b="B")


@pytest.mark.parametrize(
    ("structural", "semantic"),
    [
        ("MAYBE", "FAITHFUL"),
        ("VALID", "MAYBE"),
    ],
)
def test_unknown_outcomes_fail_closed(
    structural: str,
    semantic: str,
) -> None:
    rows = _rows()
    rows[0]["arms"]["A"] = {
        "structural_outcome": structural,
        "semantic_verdict": semantic,
    }

    with pytest.raises(ValueError, match="unsupported"):
        build_paired_vur_set(rows, arm_a="A", arm_b="B")


def test_policy_unresolved_is_visible_as_exclusion_reason() -> None:
    rows = _rows()
    rows[0]["arms"]["A"] = {
        "structural_outcome": "POLICY_UNRESOLVED",
        "semantic_verdict": "INDETERMINATE",
    }

    result = build_paired_vur_set(rows, arm_a="A", arm_b="B")

    assert result.exclusion_counts["arm_a_policy_unresolved"] == 1
