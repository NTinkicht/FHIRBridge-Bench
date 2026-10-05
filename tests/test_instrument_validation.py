import pytest

from fhirbridge.instrument_validation import (
    confusion_counts,
    evaluate_gate,
    qualify_instrument,
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
