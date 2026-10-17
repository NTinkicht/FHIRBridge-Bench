import pytest

from fhirbridge.endpoint_metrics import summarize_endpoint_states, summarize_vur


def test_vur_uses_only_structurally_valid_determinate_cases() -> None:
    summary = summarize_vur(
        [True, True, True, False, True],
        ["FAITHFUL", "UNFAITHFUL", "INDETERMINATE", "UNFAITHFUL", "FAITHFUL"],
    )

    assert summary.attempted == 5
    assert summary.structurally_valid == 4
    assert summary.structurally_invalid == 1
    assert summary.faithful == 2
    assert summary.unfaithful == 1
    assert summary.indeterminate == 1
    assert summary.determinate_denominator == 3
    assert summary.structural_validity_rate == pytest.approx(4 / 5)
    assert summary.valid_and_faithful_yield == pytest.approx(2 / 5)
    assert summary.valid_and_unfaithful_yield == pytest.approx(1 / 5)
    assert summary.valid_indeterminate_yield == pytest.approx(1 / 5)
    assert summary.vur == pytest.approx(1 / 3)
    assert summary.indeterminate_rate == pytest.approx(1 / 4)
    assert summary.best_case_vur == pytest.approx(1 / 4)
    assert summary.worst_case_vur == pytest.approx(2 / 4)


def test_all_valid_indeterminate_cases_do_not_become_zero_vur() -> None:
    summary = summarize_vur(
        [True, True],
        ["INDETERMINATE", "INDETERMINATE"],
    )

    assert summary.vur is None
    assert summary.determinate_denominator == 0
    assert summary.structural_validity_rate == 1.0
    assert summary.valid_and_faithful_yield == 0.0
    assert summary.valid_and_unfaithful_yield == 0.0
    assert summary.valid_indeterminate_yield == 1.0
    assert summary.indeterminate_rate == 1.0
    assert summary.best_case_vur == 0.0
    assert summary.worst_case_vur == 1.0


def test_no_structurally_valid_outputs_yields_no_vur() -> None:
    summary = summarize_vur(
        [False, False],
        ["UNFAITHFUL", "FAITHFUL"],
    )

    assert summary.structurally_valid == 0
    assert summary.structural_validity_rate == 0.0
    assert summary.valid_and_faithful_yield == 0.0
    assert summary.valid_and_unfaithful_yield == 0.0
    assert summary.valid_indeterminate_yield == 0.0
    assert summary.vur is None
    assert summary.indeterminate_rate is None
    assert summary.best_case_vur is None
    assert summary.worst_case_vur is None


def test_vur_summary_rejects_misaligned_or_unknown_inputs() -> None:
    with pytest.raises(ValueError, match="align"):
        summarize_vur([True], ["FAITHFUL", "UNFAITHFUL"])

    with pytest.raises(ValueError, match="unsupported semantic verdict"):
        summarize_vur([True], ["MAYBE"])

    with pytest.raises(ValueError, match="must not be empty"):
        summarize_vur([], [])


def test_four_state_structural_summary_preserves_measurement_failures() -> None:
    summary = summarize_endpoint_states(
        [
            "VALID",
            "INVALID",
            "MEASUREMENT_FAILURE",
            "POLICY_UNRESOLVED",
            "VALID",
        ],
        [
            "UNFAITHFUL",
            "FAITHFUL",
            "INDETERMINATE",
            "FAITHFUL",
            "FAITHFUL",
        ],
    )

    assert summary.attempted == 5
    assert summary.structurally_valid == 2
    assert summary.structurally_invalid == 1
    assert summary.measurement_failure == 1
    assert summary.policy_unresolved == 1
    assert summary.structural_validity_rate == pytest.approx(2 / 5)
    assert summary.structural_invalidity_rate == pytest.approx(1 / 5)
    assert summary.measurement_failure_rate == pytest.approx(1 / 5)
    assert summary.policy_unresolved_rate == pytest.approx(1 / 5)
    assert summary.valid_and_faithful_yield == pytest.approx(1 / 5)
    assert summary.valid_and_unfaithful_yield == pytest.approx(1 / 5)
    assert summary.vur == pytest.approx(1 / 2)


def test_policy_unresolved_or_measurement_failure_never_enters_vur() -> None:
    summary = summarize_endpoint_states(
        ["POLICY_UNRESOLVED", "MEASUREMENT_FAILURE"],
        ["UNFAITHFUL", "UNFAITHFUL"],
    )

    assert summary.structurally_valid == 0
    assert summary.determinate_denominator == 0
    assert summary.vur is None
    assert summary.valid_and_unfaithful_yield == 0.0


def test_four_state_summary_rejects_unknown_structural_outcome() -> None:
    with pytest.raises(ValueError, match="unsupported structural outcome"):
        summarize_endpoint_states(["MAYBE"], ["FAITHFUL"])
