import yaml

_PATH = "benchmark/lri_profile_selection.yaml"


def _selection() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_initial_lri_profile_selects_ng_fru_as_candidate() -> None:
    record = _selection()
    selection = record["profile_selection"]

    assert selection["selected_profile_name"] == "LRI_NG_FRU_Profile_V3"
    assert (
        selection["candidate_precoordinated_profile_oid"]["value"]
        == "2.16.840.1.113883.9.195.3.25"
    )
    assert selection["status"] == "selected_bounded_target_pending_independent_qualification"


def test_selected_profile_components_match_authoritative_edition5_combination() -> None:
    record = _selection()
    components = {item["name"]: item["oid"] for item in record["components"]}

    assert components == {
        "LRI_Common_Component_V3": "2.16.840.1.113883.9.195.3.22",
        "LRI_NG_Component_R1": "2.16.840.1.113883.9.13",
        "LAB_FRU_Component": "2.16.840.1.113883.9.83",
    }


def test_publication_internal_oid_conflict_fails_safe_to_component_declaration() -> None:
    record = _selection()
    conflict = record["publication_identifier_conflict"]
    msh21 = record["message_requirements"]["msh_21"]

    assert conflict["status"] == "unresolved_pending_independent_source_adjudication"
    assert conflict["section_7_4_3_page_152"]["printed_oid"].endswith(".3.25")
    assert conflict["lri_11_page_169"]["printed_oid"].endswith(".3.3")
    assert msh21["preferred_declaration_strategy"] == (
        "component_oids_pending_independent_review"
    )
    assert msh21["precoordinated_oid_declaration"]["status"].startswith("deferred")


def test_profile_selection_requires_source_grounded_order_context() -> None:
    record = _selection()
    source_requirements = set(record["benchmark_source_requirements"])

    assert "explicit_order_fact" in source_requirements
    assert "unique_source_grounded_filler_order_identifier" in source_requirements
    assert "source_grounded_ordering_provider" in source_requirements
    assert "US_Core_ServiceRequest_projection" in source_requirements
    assert "explicit_single_canonical_order_identifier_semantics" in source_requirements
    assert (
        "ServiceRequest_vs_DiagnosticReport_identifier_locus_independent_review"
        in source_requirements
    )


def test_order_semantics_stay_outside_primary_endpoint_until_review() -> None:
    record = _selection()
    semantic = set(record["scoring_boundary"]["semantic_endpoint_after_independent_review"])

    assert "order_control_value_equivalence" in semantic
    assert "filler_order_identifier_value_equivalence" in semantic
    assert "ordering_provider_identity_equivalence" in semantic
    assert "DiagnosticReport_basedOn_to_order_linkage" in semantic


def test_profile_selection_does_not_claim_machine_freeze() -> None:
    record = _selection()
    freeze_requirements = set(record["freeze_requirements"])

    assert (
        "independently_extract_all_in_scope_Common_NG_FRU_Edition5_2024DEC_requirements"
        in freeze_requirements
    )
    assert (
        "independently_adjudicate_MSH21_publication_oid_conflict_or_defer_oid"
        in freeze_requirements
    )
    assert (
        "independently_certify_bounded_denominator_and_source_completeness"
        in freeze_requirements
    )
    assert (
        "qualify_positive_and_expected_locus_negative_controls_against_G1_bounded_rules"
        in freeze_requirements
    )
    assert "acquire_machine_readable_LRI_NG_FRU_Profile_V3_bundle" not in freeze_requirements
    route = record["development_route"]
    assert route["selected"] == "bounded_independent_reconstruction"
    assert route["original_edition5_IGAMT_bundle_required_for_development"] is False
    assert route["qualified_bounded_G1_validator"] is False
    assert route["confirmatory_inference_authorized"] is False
