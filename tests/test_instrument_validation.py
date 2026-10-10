import pytest

from fhirbridge.instrument_validation import (
    confusion_counts,
    evaluate_gate,
    evaluate_gate_with_abstention,
    qualify_instrument,
    qualify_instrument_with_abstention,
)


def test_confusion_counts_match_known_binary_example() -> None:
    expert = [True, True, True, True, False, False, False, False, False, False]
    verifier = [True, True, True, False, True, False, False, False, False, False]

    counts = confusion_counts(expert, verifier)

    assert counts.true_positive == 3
    assert counts.false_negative == 1
    assert counts.false_positive == 1
    assert counts.true_negative == 5
    assert counts.total == 10


def test_qualification_metrics_match_point_estimates() -> None:
    expert = [True, True, True, True, False, False, False, False, False, False]
    verifier = [True, True, True, False, True, False, False, False, False, False]

    result = qualify_instrument(expert, verifier)

    assert result.sensitivity.estimate == pytest.approx(3 / 4)
    assert result.specificity.estimate == pytest.approx(5 / 6)
    assert result.ppv.estimate == pytest.approx(3 / 4)
    assert result.npv.estimate == pytest.approx(5 / 6)
    assert result.accuracy.estimate == pytest.approx(8 / 10)
    for metric in (
        result.sensitivity,
        result.specificity,
        result.ppv,
        result.npv,
        result.accuracy,
    ):
        assert 0 <= metric.lower <= metric.estimate <= metric.upper <= 1


def test_gate_has_no_hardcoded_thresholds_and_uses_supplied_values() -> None:
    result = qualify_instrument(
        [True, True, True, True, False, False, False, False],
        [True, True, True, True, False, False, False, False],
    )

    permissive = evaluate_gate(
        result,
        minimum_sensitivity=0.9,
        minimum_ppv=0.9,
    )
    strict_lower_bound = evaluate_gate(
        result,
        minimum_sensitivity=0.9,
        minimum_ppv=0.9,
        use_lower_confidence_bound=True,
    )

    assert permissive.passed
    assert not strict_lower_bound.passed
    assert permissive.sensitivity_threshold == 0.9
    assert permissive.ppv_threshold == 0.9


def test_undefined_metric_denominators_are_rejected() -> None:
    with pytest.raises(ValueError, match="expert positives are absent"):
        qualify_instrument([False, False], [False, True])

    with pytest.raises(ValueError, match="expert negatives are absent"):
        qualify_instrument([True, True], [True, False])

    with pytest.raises(ValueError, match="verifier positives are absent"):
        qualify_instrument([True, False], [False, False])

    with pytest.raises(ValueError, match="verifier negatives are absent"):
        qualify_instrument([True, False], [True, True])


def test_binary_input_validation_is_strict() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        confusion_counts([], [])

    with pytest.raises(ValueError, match="booleans only"):
        confusion_counts([True, 1], [True, False])

    with pytest.raises(ValueError, match="equal length"):
        confusion_counts([True], [True, False])


def test_gate_rejects_invalid_thresholds() -> None:
    result = qualify_instrument(
        [True, True, False, False],
        [True, False, False, True],
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        evaluate_gate(result, minimum_sensitivity=1.1, minimum_ppv=0.5)


def test_abstaining_verifier_reports_indeterminate_rate_separately() -> None:
    expert = [True, True, True, False, False, False]
    verdicts = [
        "UNFAITHFUL",
        "INDETERMINATE",
        "UNFAITHFUL",
        "FAITHFUL",
        "INDETERMINATE",
        "FAITHFUL",
    ]

    result = qualify_instrument_with_abstention(expert, verdicts)

    assert result.total_cases == 6
    assert result.determinate_cases == 4
    assert result.indeterminate_count == 2
    assert result.indeterminate_rate.estimate == pytest.approx(2 / 6)
    assert result.determinate_binary.sensitivity.estimate == 1.0
    assert result.determinate_binary.specificity.estimate == 1.0


def test_abstention_gate_can_fail_even_when_binary_metrics_pass() -> None:
    result = qualify_instrument_with_abstention(
        [True, True, True, False, False, False],
        [
            "UNFAITHFUL",
            "INDETERMINATE",
            "UNFAITHFUL",
            "FAITHFUL",
            "INDETERMINATE",
            "FAITHFUL",
        ],
    )

    gate = evaluate_gate_with_abstention(
        result,
        minimum_sensitivity=0.9,
        minimum_ppv=0.9,
        maximum_indeterminate_rate=0.2,
    )

    assert gate.binary_gate.passed
    assert not gate.passed
    assert gate.indeterminate_value == pytest.approx(2 / 6)


def test_abstention_gate_can_use_upper_confidence_bound() -> None:
    result = qualify_instrument_with_abstention(
        [True, True, False, False],
        ["UNFAITHFUL", "UNFAITHFUL", "FAITHFUL", "FAITHFUL"],
    )

    point_gate = evaluate_gate_with_abstention(
        result,
        minimum_sensitivity=0.9,
        minimum_ppv=0.9,
        maximum_indeterminate_rate=0.2,
    )
    upper_gate = evaluate_gate_with_abstention(
        result,
        minimum_sensitivity=0.9,
        minimum_ppv=0.9,
        maximum_indeterminate_rate=0.2,
        use_upper_confidence_bound_for_indeterminate=True,
    )

    assert point_gate.passed
    assert not upper_gate.passed
    assert upper_gate.indeterminate_value > point_gate.indeterminate_value


def test_all_indeterminate_verifier_output_is_not_binary_qualified() -> None:
    with pytest.raises(ValueError, match="every verifier verdict"):
        qualify_instrument_with_abstention(
            [True, False],
            ["INDETERMINATE", "INDETERMINATE"],
        )


def test_abstention_qualification_rejects_unknown_verdicts() -> None:
    with pytest.raises(ValueError, match="unsupported verifier semantic verdict"):
        qualify_instrument_with_abstention(
            [True, False],
            ["UNFAITHFUL", "MAYBE"],
        )


def test_abstention_gate_rejects_invalid_ceiling() -> None:
    result = qualify_instrument_with_abstention(
        [True, True, False, False],
        ["UNFAITHFUL", "UNFAITHFUL", "FAITHFUL", "FAITHFUL"],
    )

    with pytest.raises(ValueError, match="maximum_indeterminate_rate"):
        evaluate_gate_with_abstention(
            result,
            minimum_sensitivity=0.8,
            minimum_ppv=0.8,
            maximum_indeterminate_rate=1.1,
        )
