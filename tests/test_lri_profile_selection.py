import yaml

_PATH = "benchmark/lri_profile_selection.yaml"


def _selection() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_initial_lri_profile_selects_ng_fru_precoordinated_profile() -> None:
    record = _selection()
    selection = record["profile_selection"]

    assert selection["selected_profile_name"] == "LRI_NG_FRU_Profile_V3"
    assert selection["selected_profile_oid"] == "2.16.840.1.113883.9.195.3.25"
    assert selection["status"] == "selected_candidate_pending_machine_bundle"


def test_selected_profile_components_match_authoritative_edition5_combination() -> None:
    record = _selection()
    components = {item["name"]: item["oid"] for item in record["components"]}

    assert components == {
        "LRI_Common_Component_V3": "2.16.840.1.113883.9.195.3.22",
        "LRI_NG_Component_R1": "2.16.840.1.113883.9.13",
        "LAB_FRU_Component": "2.16.840.1.113883.9.83",
    }


def test_profile_selection_requires_source_grounded_order_context() -> None:
    record = _selection()
    source_requirements = set(record["benchmark_source_requirements"])

    assert "explicit_order_fact" in source_requirements
    assert "unique_source_grounded_filler_order_identifier" in source_requirements
    assert "source_grounded_ordering_provider" in source_requirements
    assert "no_DiagnosticReport_identifier_repurposing_as_order_identifier" in source_requirements


def test_profile_selection_does_not_claim_machine_freeze() -> None:
    record = _selection()
    freeze_requirements = set(record["freeze_requirements"])

    assert "acquire_machine_readable_LRI_NG_FRU_Profile_V3_bundle" in freeze_requirements
    assert "pass_local_NIST_reference_message_qualification" in freeze_requirements
    assert "pass_structural_negative_controls" in freeze_requirements
