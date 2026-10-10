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
    assert selection["status"] == "selected_candidate_pending_machine_bundle"


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

    assert conflict["status"] == "unresolved_pending_machine_bundle"
    assert conflict["section_7_4_3_page_152"]["printed_oid"].endswith(".3.25")
    assert conflict["lri_11_page_169"]["printed_oid"].endswith(".3.3")
    assert msh21["preferred_declaration_strategy"] == (
        "component_oids_until_machine_bundle"
    )
    assert msh21["precoordinated_oid_declaration"]["status"].startswith("deferred")


def test_profile_selection_requires_source_grounded_order_context() -> None:
    record = _selection()
    source_requirements = set(record["benchmark_source_requirements"])

    assert "explicit_order_fact" in source_requirements
    assert "unique_source_grounded_filler_order_identifier" in source_requirements
    assert "source_grounded_ordering_provider" in source_requirements
    assert "US_Core_ServiceRequest_projection" in source_requirements
    assert "no_DiagnosticReport_identifier_repurposing_as_order_identifier" in source_requirements


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

    assert "acquire_machine_readable_LRI_NG_FRU_Profile_V3_bundle" in freeze_requirements
    assert "resolve_precoordinated_msh21_oid_conflict" in freeze_requirements
    assert "pass_local_NIST_reference_message_qualification" in freeze_requirements
    assert "pass_structural_negative_controls" in freeze_requirements
