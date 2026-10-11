"""Safety contract for PI-selected but NOT qualified Edition 5 Path B."""

from pathlib import Path

import yaml


def _proposal() -> dict:
    path = Path("benchmark/lri_edition5_contingency_proposal.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["edition5_contingency"]


def test_candidate_does_not_change_confirmatory_freeze_authority() -> None:
    proposal = _proposal()
    assert proposal["status"] == "preferred_development_path_selected_not_qualified"
    assert proposal["selected_path"] == "bounded_independent_reconstruction"
    assert proposal["path_selection_approved"] is True
    assert proposal["path_selection_scope"] == "development_preparation_only"
    assert proposal["confirmatory_protocol_amendment_status"] == "draft_not_approved"
    assert proposal["activation_allowed"] is False
    assert proposal["confirmatory_inference_authorized"] is False
    assert proposal["replaces_existing_machine_bundle_gate"] is False
    assert not all(proposal["prerequisites"].values())


def test_reconstructed_rules_cannot_masquerade_as_original_profile() -> None:
    proposal = _proposal()
    paths = proposal["possible_paths"]
    assert paths["bounded_independent_reconstruction"]["status"] == "not_qualified"
    assert (
        paths["bounded_independent_reconstruction"][
            "may_claim_official_original_machine_profile_conformance"
        ]
        is False
    )
    assert paths["aphl_newborn_gvt"]["allowed_as_general_lab_ground_truth"] is False
    assert paths["aphl_newborn_gvt"]["import_newborn_specific_rules"] is False


def test_conformance_and_denominator_fail_closed() -> None:
    proposal = _proposal()
    assert proposal["acquisition"]["definitive_nonexistence_established"] is False
    assert proposal["acquisition"]["private_correspondence_redistribution_permitted"] is False
    assert not any(proposal["safeguards"].values())
    assert (
        proposal["possible_paths"]["bounded_independent_reconstruction"][
            "require_statistics_and_estimand_amendment"
        ]
        is True
    )


def test_path_a_is_optional_and_has_no_indefinite_development_hold() -> None:
    proposal = _proposal()
    paths = proposal["possible_paths"]
    assert paths["exact_machine_profile"]["role"] == (
        "optional_prespecified_sensitivity_and_corroboration"
    )
    assert proposal["path_a_cutoff"]["cut_off_date_fixed"] is False
    assert proposal["path_a_cutoff"]["original_bundle_if_later_found"] == (
        "prespecified_differential_sensitivity_only"
    )


def test_ai_reader_cannot_substitute_for_blind_human_standards_adjudication() -> None:
    proposal = _proposal()
    candidate = proposal["possible_paths"]["bounded_independent_reconstruction"]
    assert candidate["required_independent_extraction_channels"] == 2
    assert candidate["independent_AI_counts_as_human_expert"] is False
    assert candidate["reviewer_agreement_alone_proves_completeness"] is False
    assert candidate["require_independent_clinical_and_standards_review"] is True
