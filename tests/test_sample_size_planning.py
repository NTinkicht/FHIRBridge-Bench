import pytest

from fhirbridge.sample_size_planning import (
    approximate_mcnemar_pair_n,
    cluster_design_effect,
    inflate_required_n,
    minimum_n_for_wilson_precision,
    plan_paired_mcnemar,
    plan_proportion_precision,
    wilson_expected_half_width,
)


def test_wilson_expected_half_width_shrinks_with_sample_size() -> None:
    small = wilson_expected_half_width(50, 0.2)
    large = wilson_expected_half_width(500, 0.2)

    assert large < small


def test_minimum_n_for_wilson_precision_is_minimal() -> None:
    n = minimum_n_for_wilson_precision(0.2, 0.05)

    assert wilson_expected_half_width(n, 0.2) <= 0.05
    if n > 1:
        assert wilson_expected_half_width(n - 1, 0.2) > 0.05


def test_cluster_design_effect_is_one_without_clustering() -> None:
    assert cluster_design_effect(1.0, 0.8) == 1.0
    assert cluster_design_effect(4.0, 0.0) == 1.0
    assert cluster_design_effect(4.0, 0.2) == pytest.approx(1.6)


def test_sample_inflation_accounts_for_clustering_and_retention() -> None:
    clustered, attempted = inflate_required_n(
        100,
        design_effect=1.5,
        expected_analysis_retention=0.75,
    )

    assert clustered == 150
    assert attempted == 200


def test_proportion_precision_plan_combines_all_inflations() -> None:
    plan = plan_proportion_precision(
        expected_rate=0.2,
        target_half_width=0.05,
        mean_cluster_size=3.0,
        icc=0.1,
        expected_analysis_retention=0.8,
    )

    assert plan.independent_row_n > 0
    assert plan.design_effect == pytest.approx(1.2)
    assert plan.cluster_inflated_row_n >= plan.independent_row_n
    assert plan.attempted_row_n >= plan.cluster_inflated_row_n
    assert plan.planned_source_cluster_count == (
        -(-plan.attempted_row_n // 3)
    )


def test_mcnemar_required_n_increases_as_discordant_difference_shrinks() -> None:
    larger_difference = approximate_mcnemar_pair_n(p10=0.20, p01=0.05)
    smaller_difference = approximate_mcnemar_pair_n(p10=0.15, p01=0.10)

    assert smaller_difference > larger_difference


def test_paired_mcnemar_plan_is_labeled_planning_approximation() -> None:
    plan = plan_paired_mcnemar(
        p10=0.20,
        p01=0.05,
        mean_cluster_size=2.0,
        icc=0.1,
        expected_pair_retention=0.85,
        alpha=0.05,
        power=0.80,
    )

    assert plan.independent_pair_row_n > 0
    assert (
        plan.cluster_inflated_pair_row_n
        >= plan.independent_pair_row_n
    )
    assert (
        plan.attempted_pair_row_n
        >= plan.cluster_inflated_pair_row_n
    )
    assert plan.planned_source_cluster_count == (
        -(-plan.attempted_pair_row_n // 2)
    )
    assert plan.method == "normal_approximation_for_planning_only"


@pytest.mark.parametrize(
    ("p10", "p01"),
    [(0.1, 0.1), (0.8, 0.4)],
)
def test_mcnemar_planning_rejects_uninformative_probabilities(
    p10: float,
    p01: float,
) -> None:
    with pytest.raises(ValueError):
        approximate_mcnemar_pair_n(p10=p10, p01=p01)


@pytest.mark.parametrize(
    ("mean_cluster_size", "icc"),
    [(0.9, 0.1), (2.0, -0.1), (2.0, 1.1)],
)
def test_design_effect_rejects_invalid_inputs(
    mean_cluster_size: float,
    icc: float,
) -> None:
    with pytest.raises(ValueError):
        cluster_design_effect(mean_cluster_size, icc)


def test_retention_must_be_nonzero() -> None:
    with pytest.raises(ValueError, match="expected_analysis_retention"):
        inflate_required_n(
            100,
            design_effect=1.0,
            expected_analysis_retention=0.0,
        )
