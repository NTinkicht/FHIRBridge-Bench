"""PI Path B development decision must never be mistaken for research qualification."""

from pathlib import Path

import yaml


def _read(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_pi_selects_path_b_only_for_development() -> None:
    record = _read("benchmark/lri_edition5_contingency_proposal.yaml")[
        "edition5_contingency"
    ]
    assert record["selected_path"] == "bounded_independent_reconstruction"
    assert record["path_selection_approved"] is True
    assert record["activation_allowed"] is False
    assert record["replaces_existing_machine_bundle_gate"] is False
    assert record["confirmatory_inference_authorized"] is False
    assert record["confirmatory_protocol_amendment_status"] == (
        "draft_not_approved"
    )
    assert not all(record["prerequisites"].values())


def test_qualified_bounded_claim_requires_unknown_review_denominator() -> None:
    coverage = _read("benchmark/path_b_bounded_coverage.yaml")[
        "path_b_bounded_coverage"
    ]
    scope = coverage["bounded_segments"]
    assert {x["segment"] for x in scope} == {
        "MSH", "PID", "ORC", "OBR", "OBX", "SPM", "NTE"
    }
    assert next(x for x in scope if x["segment"] == "NTE")["included"] == (
        "if_present"
    )
    assert not any(x["R_and_C_constraints_audited"] for x in scope)
    inventory = coverage["required_and_conditional_inventory"]
    assert inventory["independent_denominator"] is None
    assert inventory["published_percentage"] is None
    assert inventory["zero_unreviewed_in_scope_R_or_C_required"] is True
    assert inventory["unresolved_mandatory_rules_are_qualified_passes"] is False
    assert coverage["claims"]["original_IGAMT_profile_conformant"] is False
    assert coverage["claims"]["confirmatory_G1_validity_authorized"] is False


def test_pi_direction_does_not_clear_existing_protocol_blockers() -> None:
    gates = _read("benchmark/protocol_freeze_gates.yaml")
    assert gates["protocol_freeze"]["status"] == "blocked"
    direction = gates["protocol_freeze"]["development_path_decision"]
    assert direction["selected"] == "bounded_independent_reconstruction"
    assert direction["confirmatory_permission"] is False
    assert direction["gated_qualification_alternative_implemented"] is False
    assert len(gates["gates"]) == 12
    assert all(gate["status"] == "blocked" for gate in gates["gates"])
    assert sum(len(gate["blockers"]) for gate in gates["gates"]) == 31


def test_estimand_redesign_does_not_reward_unsafe_valid_outputs() -> None:
    proposed = _read("analysis/path_b_estimand_candidate.yaml")[
        "path_b_estimand_candidate"
    ]
    assert proposed["PI_approved_development_direction"] is True
    assert proposed["PI_approved_confirmatory_estimand"] is False
    assert proposed["confirmatory_execution_authorized"] is False
    joint = proposed["estimands"]
    assert joint["candidate_primary"]["denominator"] == "all_attempts"
    assert joint["companion_safety"]["denominator"] == "all_attempts"
    assert (
        joint["companion_safety"]["interpretation"]
        == "unsafe_valid_outputs_not_an_improvement_goal"
    )
    assert (
        joint["descriptive_conditional"][
            "no_implicit_both_arms_valid_paired_primary_test"
        ]
        is True
    )
    assert not all(proposed["prerequisites"].values())


def test_original_profile_pins_stay_unqualified_and_strict() -> None:
    tooling = _read("benchmark/tooling_versions.yaml")
    v2 = tooling["structural_validation"]["hl7v2"]
    assert v2["profile_validation_qualification_passed"] is False
    assert v2["profile_artifact"] == "unresolved"

    profile = _read("benchmark/hl7v2_lri_profile_pin.yaml")
    assert profile["profile_pin"]["status"] != "frozen"
    assert profile["qualification"]["structural_negative_controls_passed"] is False


def test_reviewer_AI_does_not_replace_independent_human_standards_check() -> None:
    plan = _read("benchmark/lri_edition5_contingency_proposal.yaml")[
        "edition5_contingency"
    ]["possible_paths"]["bounded_independent_reconstruction"]
    assert plan["independent_AI_counts_as_human_expert"] is False
    assert plan["require_independent_clinical_and_standards_review"] is True

    coverage = _read("benchmark/path_b_bounded_coverage.yaml")[
        "path_b_bounded_coverage"
    ]
    assert coverage["reviews"]["standards_completeness_certified"] is False
    assert coverage["reviews"]["all_disagreements_adjudicated"] is False
