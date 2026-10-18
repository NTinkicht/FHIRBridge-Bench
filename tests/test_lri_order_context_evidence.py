import yaml

_PATH = "benchmark/lri_order_context_evidence.yaml"


def _record() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_authoritative_edition5_publication_resolves_base_order_context() -> None:
    record = _record()

    assert (
        record["evidence_record"]["decision_status"]
        == "order_context_resolved_from_authoritative_edition5_publication"
    )
    resolved = record["freeze_decision"]["resolved_from_authoritative_publication"]
    assert resolved["ORC_usage"] == "R"
    assert resolved["ORC_cardinality"] == "1..1"
    assert resolved["OBR_usage"] == "R"
    assert resolved["OBR_cardinality"] == "1..1"
    assert resolved["order_control_usage"] == "R"
    assert resolved["filler_order_identifier_usage"] == "R"
    assert resolved["ordering_provider_usage"] == "R"


def test_publication_package_is_not_promoted_to_machine_profile_bundle() -> None:
    record = _record()

    package = record["authoritative_publication"][
        "locally_acquired_publication_package"
    ]
    assert package["contains_machine_readable_profile_xml"] is False
    assert (
        record["freeze_decision"][
            "exact_edition5_profile_bundle_required_for_machine_validation"
        ]
        is True
    )
    prohibited = set(record["freeze_decision"]["prohibited_shortcuts"])
    assert "infer_machine_profile_from_human_readable_pdf" in prohibited


def test_profile_selection_is_synchronized_as_candidate() -> None:
    record = _record()

    assert (
        record["edition5_profile_architecture"]["selected_confirmatory_combination"]
        == "LRI_NG_FRU_Profile_V3_bounded_target_pending_independent_qualification"
    )
    assert (
        record["edition5_profile_architecture"]["selection_record"]
        == "benchmark/lri_profile_selection.yaml"
    )


def test_msh21_uses_consistent_component_oids_until_machine_bundle() -> None:
    record = _record()
    strategy = record["freeze_decision"]["msh21_prefreeze_strategy"]

    assert strategy["use_precoordinated_oid"] is False
    assert strategy["use_component_oids"] == [
        "2.16.840.1.113883.9.195.3.22",
        "2.16.840.1.113883.9.13",
        "2.16.840.1.113883.9.83",
    ]
    assert strategy["defer_precoordinated_oid_until_independent_disposition_of_conflict"]


def test_pdf_page_anchors_cover_load_bearing_order_claims() -> None:
    record = _record()
    anchors = record["authoritative_publication"]["page_anchors"]

    assert 156 in anchors["abstract_message_syntax"]["pages"]
    assert 185 in anchors["ORC_table_and_constraints"]["pages"]
    assert 188 in anchors["ORC_table_and_constraints"]["pages"]
    assert 189 in anchors["OBR_table"]["pages"]
    assert 190 in anchors["OBR_table"]["pages"]


def test_legacy_and_local_sources_cannot_define_confirmatory_order_semantics() -> None:
    record = _record()

    assert record["legacy_nist_comparator"]["role"] == "historical_differential_only"
    assert (
        record["secondary_implementation_evidence"]["role"]
        == "corroborating_secondary_only"
    )
    prohibited = set(record["freeze_decision"]["prohibited_shortcuts"])
    assert "infer_edition5_from_legacy_r2" in prohibited
    assert "infer_edition5_from_michigan_local_profile" in prohibited
    assert "invent_order_identifiers_to_make_validator_green" in prohibited


def test_safe_order_context_path_preserves_source_grounding_boundary() -> None:
    record = _record()

    text = record["freeze_decision"]["safe_source_grounded_path"]
    assert "canonical order fact" in text
    assert "ServiceRequest" in text
    assert "ORC/OBR" in text
    assert "outside the primary endpoint" in text


def test_exact_publication_hashes_are_pinned() -> None:
    record = _record()
    package = record["authoritative_publication"][
        "locally_acquired_publication_package"
    ]

    assert len(package["package_sha256"]) == 64
    assert len(package["implementation_guide_pdf"]["sha256"]) == 64
    assert len(package["errata_letter_pdf"]["sha256"]) == 64
