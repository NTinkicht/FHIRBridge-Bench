"""Safety contract for the non-active Edition 5 contingency proposal."""

from pathlib import Path

import yaml


def _proposal() -> dict:
    path = Path("benchmark/lri_edition5_contingency_proposal.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["edition5_contingency"]


def test_candidate_does_not_change_confirmatory_freeze_authority() -> None:
    proposal = _proposal()
    assert proposal["status"] == "draft_not_approved"
    assert proposal["selected_path"] == "none"
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
