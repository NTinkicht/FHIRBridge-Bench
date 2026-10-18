from copy import deepcopy

import yaml

from fhirbridge.mapping_context import (
    build_frozen_mapping_context,
    mapping_context_json,
)

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
_STATUS = "benchmark/status_mapping_candidates.yaml"
_SPECIMEN = "benchmark/specimen_binding_candidates.yaml"
_PROFILE = "benchmark/hl7v2_lri_profile_pin.yaml"


def _yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _frozen_inputs() -> tuple[dict, dict, dict, dict]:
    contract = deepcopy(_yaml(_CONTRACT))
    status = deepcopy(_yaml(_STATUS))
    specimen = deepcopy(_yaml(_SPECIMEN))
    profile = deepcopy(_yaml(_PROFILE))

    contract["contract"]["freeze_status"] = "frozen"
    contract["contract"]["status"] = "frozen"
    for rule in contract["rules"]:
        if rule["projectability"] != "INDETERMINATE":
            rule["status"] = "frozen"
    for guard in contract["grounding_guards"]:
        guard["status"] = "frozen"

    status["status_mapping_candidates"]["status"] = "frozen"
    specimen["specimen_binding_candidates"]["status"] = "frozen"

    profile["profile_pin"]["status"] = "frozen"
    for section, key in (
        ("identity_verification", "profile_identity_guard_passed"),
        ("identity_verification", "edition_5_evidence_checked"),
        ("identity_verification", "errata_2024dec_evidence_checked"),
        ("identity_verification", "independent_profile_provenance_reviewed"),
        ("qualification", "local_reference_messages_passed"),
        ("qualification", "structural_negative_controls_passed"),
        ("qualification", "warning_error_policy_frozen"),
    ):
        profile[section][key] = True

    return contract, status, specimen, profile


def test_current_repository_artifacts_cannot_build_confirmatory_mapping_context() -> None:
    try:
        build_frozen_mapping_context(
            _yaml(_CONTRACT),
            _yaml(_STATUS),
            _yaml(_SPECIMEN),
            _yaml(_PROFILE),
        )
    except ValueError as exc:
        assert "not frozen" in str(exc)
    else:
        raise AssertionError("draft artifacts unexpectedly built mapping context")


def test_frozen_context_excludes_indeterminate_rules() -> None:
    contract, status, specimen, profile = _frozen_inputs()

    context = build_frozen_mapping_context(
        contract,
        status,
        specimen,
        profile,
    )

    included = {item["rule_id"] for item in context["rules"]}
    excluded = set(context["excluded_indeterminate_rule_ids"])
    assert "PATIENT_IDENTIFIER_001" in included
    assert "ORDER_IDENTIFIER_MAPPING_001" not in included
    assert "ORDER_IDENTIFIER_MAPPING_001" in excluded
    assert "ORDER_REQUESTER_MAPPING_001" in excluded
    assert "ORDER_CODE_MAPPING_001" in excluded
    assert "REPORT_BASEDON_ORDER_001" in excluded


def test_mapping_context_does_not_leak_measurement_labels_or_severity() -> None:
    contract, status, specimen, profile = _frozen_inputs()

    text = mapping_context_json(
        build_frozen_mapping_context(
            contract,
            status,
            specimen,
            profile,
        )
    )

    assert '"failure_types"' not in text
    assert '"severity_default"' not in text
    assert '"evidence"' not in text
    assert '"expert_review_required"' not in text


def test_mapping_context_contains_only_frozen_reviewed_status_and_specimen_maps() -> None:
    contract, status, specimen, profile = _frozen_inputs()

    context = build_frozen_mapping_context(
        contract,
        status,
        specimen,
        profile,
    )

    assert context["status_maps"]["diagnostic_report_status_to_OBR_25"]["final"] == "F"
    assert context["status_maps"]["observation_status_to_OBX_11"]["final"] == "F"
    assert context["specimen_maps"]["serum_to_SPM_4"]["candidate_code"] == "SER"
    assert (
        context["specimen_maps"]["venipuncture_to_SPM_7"]["candidate_code"]
        == "VENIP"
    )


def test_mapping_context_refuses_unqualified_profile_even_if_contract_is_frozen() -> None:
    contract, status, specimen, profile = _frozen_inputs()
    profile["qualification"]["structural_negative_controls_passed"] = False

    try:
        build_frozen_mapping_context(contract, status, specimen, profile)
    except ValueError as exc:
        assert "profile qualification is incomplete" in str(exc)
        assert "structural_negative_controls_passed" in str(exc)
    else:
        raise AssertionError("unqualified profile unexpectedly built context")


def test_mapping_context_refuses_unfrozen_determinate_rule() -> None:
    contract, status, specimen, profile = _frozen_inputs()
    target = next(
        rule
        for rule in contract["rules"]
        if rule["rule_id"] == "PATIENT_IDENTIFIER_001"
    )
    target["status"] = "draft"

    try:
        build_frozen_mapping_context(contract, status, specimen, profile)
    except ValueError as exc:
        assert "determinate rule is not frozen" in str(exc)
        assert "PATIENT_IDENTIFIER_001" in str(exc)
    else:
        raise AssertionError("unfrozen determinate rule unexpectedly built context")


def test_mapping_context_preserves_scoped_order_identifier_provenance() -> None:
    contract, status, specimen, profile = _frozen_inputs()
    context = build_frozen_mapping_context(contract, status, specimen, profile)
    guards = {
        item["guard_id"]: item for item in context["grounding_guards"]
    }
    order_guard = guards["ORDER_IDENTIFIER_SOURCE_GROUNDING_001"]
    assert order_guard["source_fact_type"] == "order"
    assert order_guard["additional_source_fact_types"] == ["diagnostic_report"]
    assert order_guard["additional_source_relation_type"] == "has_report"
    assert '"additional_source_relation_type":"has_report"' in (
        mapping_context_json(context)
    )
