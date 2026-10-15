"""Path B records must not silently regress to obsolete original XML acquisition."""

from pathlib import Path

import yaml


def _yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_three_records_keep_path_b_distinct_from_optional_machine_profile() -> None:
    selection = _yaml("benchmark/lri_profile_selection.yaml")
    order = _yaml("benchmark/lri_order_context_evidence.yaml")
    pin = _yaml("benchmark/hl7v2_lri_profile_pin.yaml")
    contract = _yaml("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
    contingency = _yaml("benchmark/lri_edition5_contingency_proposal.yaml")
    gate = _yaml("benchmark/protocol_freeze_gates.yaml")

    assert selection["profile_selection"]["selected_profile_name"] == "LRI_NG_FRU_Profile_V3"
    assert (
        selection["development_route"]["selected"]
        == contingency["edition5_contingency"]["selected_path"]
        == gate["protocol_freeze"]["development_path_decision"]["selected"]
        == "bounded_independent_reconstruction"
    )
    route = selection["development_route"]
    order_freeze = order["freeze_decision"]
    assert route["original_edition5_IGAMT_bundle_required_for_development"] is False
    assert order_freeze["exact_edition5_profile_bundle_required_for_path_b_development"] is False
    assert order_freeze["exact_edition5_profile_bundle_required_for_machine_validation"] is True
    assert "optional" in pin["profile_pin"]["purpose"].lower()
    assert contract["target"]["selected_validation_route"] == (
        "bounded_PDF_derived_Path_B_pending_independent_qualification"
    )
    assert contract["target"]["exact_machine_profile_status"] == (
        "optional_path_a_original_profile_unavailable"
    )
    assert contract["target"]["bounded_G1_qualification_complete"] is False
    assert contract["target"]["confirmatory_inference_authorized"] is False
    assert contract["contract"]["freeze_status"] == "not_frozen"
    assert pin["identity_verification"]["independent_profile_provenance_reviewed"] is False


def test_no_premature_oid_or_g1_claims_in_selected_target_records() -> None:
    selection = _yaml("benchmark/lri_profile_selection.yaml")
    order = _yaml("benchmark/lri_order_context_evidence.yaml")
    gate = _yaml("benchmark/protocol_freeze_gates.yaml")

    assert selection["publication_identifier_conflict"]["status"] == (
        "unresolved_pending_independent_source_adjudication"
    )
    assert selection["message_requirements"]["msh_21"]["precoordinated_oid_declaration"][
        "status"
    ] == "deferred_due_to_publication_internal_conflict"
    assert "use_conflicted_precoordinated_msh21_oid_without_independent_disposition" in (
        order["freeze_decision"]["prohibited_shortcuts"]
    )
    assert not order["freeze_decision"]["independent_G1_qualified"]
    assert not order["freeze_decision"]["confirmatory_inference_authorized"]
    assert not selection["development_route"]["confirmed_completeness_of_required_rules"]
    assert not selection["development_route"]["qualified_bounded_G1_validator"]
    assert gate["protocol_freeze"]["status"] == "blocked"
    development = gate["protocol_freeze"]["development_path_decision"]
    assert development["confirmatory_permission"] is False
    assert development["gated_qualification_alternative_implemented"] is False


def test_all_path_b_freeze_requirements_are_evidence_producing_not_original_bundle() -> None:
    selection = _yaml("benchmark/lri_profile_selection.yaml")
    required = selection["freeze_requirements"]
    assert len(required) >= 8
    assert all("machine_readable" not in x.lower() for x in required)
    assert all("NIST_reference" not in x for x in required)
    assert "show_source_grounded_feasibility_all_11_retained_LAB_families" in required
    assert "independently_approve_warning_policy_estimand_and_prospective_protocol" in required
