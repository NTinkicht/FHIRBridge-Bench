import math

import pytest

from fhirbridge.agreement import agreement_statistics


def test_perfect_multicategory_agreement_is_one() -> None:
    labels = ["MUST_PRESERVE", "MAY_TRANSFORM", "INDETERMINATE", "MUST_PRESERVE"]

    result = agreement_statistics(labels, labels)

    assert result.n == 4
    assert result.raw_agreement == 1.0
    assert result.cohens_kappa == 1.0
    assert result.gwets_ac1 == 1.0
    assert result.confusion_matrix["MUST_PRESERVE"]["MUST_PRESERVE"] == 2


def test_known_binary_example_matches_hand_calculation() -> None:
    rater_a = ["A", "A", "A", "B", "B", "B", "B", "B", "B", "B"]
    rater_b = ["A", "A", "B", "A", "B", "B", "B", "B", "B", "B"]

    result = agreement_statistics(rater_a, rater_b)

    observed = 0.8
    expected_kappa = (3 / 10) * (3 / 10) + (7 / 10) * (7 / 10)
    expected_kappa_value = (observed - expected_kappa) / (1 - expected_kappa)
    pooled_a = 6 / 20
    pooled_b = 14 / 20
    expected_ac1 = pooled_a * (1 - pooled_a) + pooled_b * (1 - pooled_b)
    expected_ac1_value = (observed - expected_ac1) / (1 - expected_ac1)

    assert math.isclose(result.raw_agreement, observed)
    assert math.isclose(result.cohens_kappa, expected_kappa_value)
    assert math.isclose(result.gwets_ac1, expected_ac1_value)
    assert result.confusion_matrix["A"]["B"] == 1
    assert result.confusion_matrix["B"]["A"] == 1


def test_single_category_perfect_agreement_is_supported() -> None:
    result = agreement_statistics(["MUST_PRESERVE"] * 5, ["MUST_PRESERVE"] * 5)

    assert result.raw_agreement == 1.0
    assert result.cohens_kappa == 1.0
    assert result.gwets_ac1 == 1.0


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="equal length"):
        agreement_statistics(["A"], ["A", "B"])


def test_empty_reviews_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        agreement_statistics([], [])
