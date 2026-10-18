from pathlib import Path

import yaml

_DESIGN = Path("analysis/core_confirmatory_design.yaml")
_TEMPLATE = Path("analysis/examples/analysis_preregistration_template.yaml")


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_analysis_preregistration_template_matches_predeclared_design() -> None:
    design = _yaml(_DESIGN)["analysis_design"]
    template = _yaml(_TEMPLATE)

    base_pairs = design["paired_secondary_comparison_family"][
        "base_comparisons"
    ]
    template_pairs = template["paired_comparisons"]["comparison_family"]
    model_key = template["paired_comparisons"]["model_keys"][0]
    expected_pairs = [
        {
            "comparison_id": f"{model_key}__{item['comparison_id']}",
            "model_key": model_key,
            "arm_a": item["arm_a"],
            "arm_b": item["arm_b"],
        }
        for item in base_pairs
    ]

    assert template_pairs == expected_pairs
    assert template["multiplicity"]["secondary_pairwise_method"] == (
        design["paired_secondary_comparison_family"]["multiplicity_method"]
    )
    assert template["paired_comparisons"]["cluster_id_field"] == (
        design["paired_analysis"]["cluster_id_field"]
    )
    assert template["paired_comparisons"]["analysis_set_rule"] == (
        design["paired_analysis"]["VUR_analysis_set_rule"]
    )
    assert template["bootstrap"]["method"] == (
        design["paired_analysis"]["bootstrap"]["method"]
    )
    assert template["bootstrap"]["iterations"] == (
        design["paired_analysis"]["bootstrap"]["iterations"]
    )
    assert template["bootstrap"]["seed"] == (
        design["paired_analysis"]["bootstrap"]["seed"]
    )
    assert template["bootstrap"]["confidence_level"] == (
        design["paired_analysis"]["bootstrap"]["confidence_level"]
    )
    assert template["mcnemar"] == design["paired_analysis"]["mcnemar"]


def test_core_design_contains_all_six_unordered_pairs_of_four_arms() -> None:
    design = _yaml(_DESIGN)["analysis_design"]
    arms = {item["arm_id"] for item in design["core_arms"]}
    comparisons = design["paired_secondary_comparison_family"][
        "base_comparisons"
    ]

    assert len(arms) == 4
    assert len(comparisons) == 6
    observed_pairs = {
        frozenset((item["arm_a"], item["arm_b"]))
        for item in comparisons
    }
    assert len(observed_pairs) == 6
    assert all(len(pair) == 2 for pair in observed_pairs)
    assert set().union(*observed_pairs) == arms


def test_analysis_design_remains_predeclared_and_not_falsely_complete() -> None:
    design = _yaml(_DESIGN)["analysis_design"]

    assert design["status"] == "predeclared_before_confirmatory_inference"
    unresolved = set(design["unresolved_before_final_preregistration"])
    assert "frozen_input_hashes" in unresolved
    assert "pilot_derived_primary_vur_hypothesis_preregistration" in unresolved
    assert "pilot_derived_sample_size_justification" in unresolved
