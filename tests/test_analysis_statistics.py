import pytest

from fhirbridge.analysis_statistics import (
    clustered_paired_risk_difference_bootstrap,
    exact_mcnemar,
    holm_adjust,
    paired_risk_difference,
    wilson_interval,
)


def test_wilson_interval_is_bounded_and_contains_estimate() -> None:
    interval = wilson_interval(5, 10)

    assert interval.estimate == 0.5
    assert 0.0 < interval.lower < 0.5
    assert 0.5 < interval.upper < 1.0
    assert interval.method == "Wilson_95_percent"


def test_wilson_interval_handles_boundary_counts() -> None:
    none = wilson_interval(0, 10)
    all_success = wilson_interval(10, 10)

    assert none.estimate == 0.0
    assert none.lower == 0.0
    assert 0.0 < none.upper < 1.0
    assert all_success.estimate == 1.0
    assert 0.0 < all_success.lower < 1.0
    assert all_success.upper == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("successes", "total"),
    [(-1, 10), (11, 10), (0, 0)],
)
def test_wilson_interval_rejects_invalid_counts(
    successes: int,
    total: int,
) -> None:
    with pytest.raises(ValueError):
        wilson_interval(successes, total)


def test_paired_risk_difference_reports_discordant_pair_counts() -> None:
    summary = paired_risk_difference(
        [1, 1, 0, 0, 1],
        [1, 0, 1, 0, 0],
    )

    assert summary.n == 5
    assert summary.risk_a == pytest.approx(3 / 5)
    assert summary.risk_b == pytest.approx(2 / 5)
    assert summary.difference == pytest.approx(1 / 5)
    assert summary.a_positive_b_negative == 2
    assert summary.a_negative_b_positive == 1


def test_exact_mcnemar_returns_one_without_discordance() -> None:
    result = exact_mcnemar([0, 1, 1], [0, 1, 1])

    assert result.discordant_pairs == 0
    assert result.p_value == 1.0


def test_exact_mcnemar_matches_two_sided_binomial_for_four_to_zero() -> None:
    result = exact_mcnemar(
        [1, 1, 1, 1],
        [0, 0, 0, 0],
    )

    assert result.a_positive_b_negative == 4
    assert result.a_negative_b_positive == 0
    assert result.discordant_pairs == 4
    assert result.p_value == pytest.approx(0.125)


def test_clustered_paired_bootstrap_is_deterministic_and_cluster_based() -> None:
    first = clustered_paired_risk_difference_bootstrap(
        [1, 0, 1, 1, 0, 0],
        [0, 0, 1, 0, 1, 0],
        ["A", "A", "B", "B", "C", "C"],
        iterations=500,
        seed=20261010,
    )
    second = clustered_paired_risk_difference_bootstrap(
        [1, 0, 1, 1, 0, 0],
        [0, 0, 1, 0, 1, 0],
        ["A", "A", "B", "B", "C", "C"],
        iterations=500,
        seed=20261010,
    )

    assert first == second
    assert first.cluster_count == 3
    assert first.estimate == pytest.approx(1 / 6)
    assert first.lower <= first.estimate <= first.upper
    assert first.iterations == 500
    assert first.seed == 20261010


def test_clustered_bootstrap_requires_two_clusters_and_enough_iterations() -> None:
    with pytest.raises(ValueError, match="at least two clusters"):
        clustered_paired_risk_difference_bootstrap(
            [1, 0],
            [0, 0],
            ["A", "A"],
            iterations=100,
            seed=1,
        )

    with pytest.raises(ValueError, match="at least 100"):
        clustered_paired_risk_difference_bootstrap(
            [1, 0],
            [0, 0],
            ["A", "B"],
            iterations=99,
            seed=1,
        )


def test_holm_adjust_preserves_original_order_and_monotonic_correction() -> None:
    adjusted = holm_adjust([0.01, 0.04, 0.03])

    assert adjusted == pytest.approx((0.03, 0.06, 0.06))


@pytest.mark.parametrize(
    "values",
    [[], [-0.1], [1.1], [0.1, "bad"]],
)
def test_holm_adjust_rejects_invalid_inputs(values) -> None:
    with pytest.raises(ValueError):
        holm_adjust(values)
