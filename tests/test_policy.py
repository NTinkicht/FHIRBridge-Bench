from copy import deepcopy

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.faults import fabricate_observation, misattribute_result_to_patient
from fhirbridge.schema_validation import load_yaml
from fhirbridge.verifier import (
    EquivalenceResult,
    FrozenMappingTerminologyEquivalence,
    LiftedFact,
    classify_graph,
    compile_verification_policy,
)

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


class _LabUnitProvider:
    def equivalent(
        self,
        source_value: float,
        source_unit: str,
        target_value: float,
        target_unit: str,
    ) -> EquivalenceResult:
        if source_unit == "mg/dL" and target_unit == "g/L":
            equivalent = abs(source_value * 0.01 - target_value) < 1e-12
        else:
            equivalent = source_unit == target_unit and source_value == target_value
        return EquivalenceResult(
            equivalent=equivalent,
            rationale_code="TEST_UCUM_EQUIVALENT" if equivalent else "TEST_UCUM_MISMATCH",
            details={
                "source_value": source_value,
                "source_unit": source_unit,
                "target_value": target_value,
                "target_unit": target_unit,
            },
        )


class _UnavailableUnitProvider:
    def equivalent(self, *args, **kwargs) -> EquivalenceResult:
        raise RuntimeError("qualified UCUM provider unavailable")


def _lift_graph(graph: dict) -> list[LiftedFact]:
    lifted: list[LiftedFact] = []
    for fact in graph["facts"]:
        relationships = tuple(
            (relation["relation_type"], f"lifted::{relation['target_fact_id']}")
            for relation in fact.get("relations", [])
        )
        payload = deepcopy(fact)
        payload["subject_ref"] = (
            f"lifted::{fact['subject_ref']}" if fact.get("subject_ref") else None
        )
        payload["relations"] = [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ]
        lifted.append(
            LiftedFact(
                lifted_fact_id=f"lifted::{fact['fact_id']}",
                fact_type=fact["fact_type"],
                subject_ref=payload["subject_ref"],
                semantic_payload=payload,
                target_paths=(f"fixture/{fact['fact_id']}",),
                relationships=relationships,
            )
        )
    return lifted


def test_contract_policy_includes_declared_fields_and_excludes_report_identifier() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    policy = compile_verification_policy(contract)

    assert policy.contract_id == "F2V-LAB-ORU-R01-001"
    assert policy.scores("patient_identity", "identifiers")
    assert policy.scores("diagnostic_report", "concept")
    assert policy.scores("diagnostic_report", "temporal.recorded_at")
    assert policy.scores("observation", "attributes.value_code")
    assert policy.scores("specimen", "attributes.collection_method_label")
    assert not policy.scores("diagnostic_report", "identifiers")
    assert not policy.scores("observation", "subject_ref")


def test_contract_policy_retains_projectability_and_rule_ids_per_scored_field() -> None:
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    assert (
        policy.projectability("diagnostic_report", "temporal.recorded_at")
        == "MUST_PRESERVE"
    )
    assert policy.projectability("observation", "unit") == "MAY_TRANSFORM"
    assert policy.projectability("observation", "value") == "MUST_PRESERVE"
    assert policy.projectability("diagnostic_report", "identifiers") is None

    assert policy.rules_for_field("diagnostic_report", "temporal.recorded_at") == (
        "REPORT_ISSUED_TIME_001",
    )
    assert policy.rules_for_field("observation", "unit") == (
        "OBSERVATION_UNIT_001",
    )
    assert policy.rules_for_field("observation", "value") == (
        "OBSERVATION_VALUE_001",
    )
    assert policy.rules_for_field("diagnostic_report", "identifiers") == ()

    assert policy.allows_operation("observation", "concept", "CODE_TRANSLATE")
    assert policy.allows_operation("observation", "value", "UNIT_CONVERT")
    assert policy.allows_operation("observation", "unit", "UNIT_CONVERT")
    assert not policy.allows_operation(
        "patient_identity",
        "identifiers",
        "UNIT_CONVERT",
    )
    assert policy.allowed_operations("diagnostic_report", "identifiers") == frozenset()


def test_contract_policy_retains_explicit_forbidden_inference_rule() -> None:
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    assert policy.must_not_infer_rule_ids == ("FREE_TEXT_INFERENCE_001",)
    assert policy.forbids_ungrounded_inference is True


def test_unfrozen_report_identifier_mapping_is_not_scored_by_contract_policy() -> None:
    source = generate_lab_scenario("LAB-001", 9201)
    target_graph = deepcopy(source)
    report = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "diagnostic_report"
    )
    report["identifiers"][0]["value"] = "DIFFERENT-ACCESSION"

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    result = classify_graph(source["facts"], _lift_graph(target_graph), policy=policy)

    assert result.faithful
    assert all(
        decision.classification == "VERIFIED_EQUIVALENT"
        for decision in result.decisions
    )


def test_declared_report_issued_time_remains_scored_by_contract_policy() -> None:
    source = generate_lab_scenario("LAB-001", 9202)
    target_graph = deepcopy(source)
    report = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "diagnostic_report"
    )
    report["temporal"]["recorded_at"] = "2026-02-01T00:00:00+00:00"

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    result = classify_graph(source["facts"], _lift_graph(target_graph), policy=policy)

    assert not result.faithful
    assert any(
        decision.classification == "CORRUPTION"
        and decision.error_subtype == "temporal"
        and "recorded_at" in decision.evidence
        for decision in result.decisions
    )


def test_absent_required_report_issued_time_is_classified_as_omission() -> None:
    source = generate_lab_scenario("LAB-001", 9203)
    target_graph = deepcopy(source)
    report = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "diagnostic_report"
    )
    report["temporal"]["recorded_at"] = None

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    result = classify_graph(source["facts"], _lift_graph(target_graph), policy=policy)

    assert not result.faithful
    omissions = [
        decision
        for decision in result.decisions
        if decision.classification == "OMISSION"
        and decision.evidence.get("omitted_field") == "temporal.recorded_at"
    ]
    assert omissions
    assert omissions[0].evidence["projectability"] == "MUST_PRESERVE"


def test_unfrozen_relationship_mapping_is_not_scored_by_contract_policy() -> None:
    source = generate_lab_scenario("LAB-005", 9204)
    target_graph = deepcopy(source)
    report = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "diagnostic_report"
    )
    assert len(report["relations"]) >= 2
    report["relations"] = report["relations"][1:]

    lifted = _lift_graph(target_graph)
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    assert not policy.scores("diagnostic_report", "relations")

    scoped = classify_graph(source["facts"], lifted, policy=policy)
    assert scoped.faithful
    assert all(
        not (
            decision.classification == "CORRUPTION"
            and decision.error_subtype == "relationship"
        )
        for decision in scoped.decisions
    )

    development_diagnostic = classify_graph(source["facts"], lifted)
    assert not development_diagnostic.faithful
    assert any(
        decision.classification == "MISATTRIBUTION"
        and decision.error_subtype == "attribution"
        and decision.evidence.get("rationale_code")
        == "WRONG_RELATIONSHIP_ATTRIBUTION"
        for decision in development_diagnostic.decisions
    )


def test_unreviewed_subject_misattribution_is_diagnostic_not_confirmatory() -> None:
    source = generate_lab_scenario("LAB-001", 9205)
    observation_id = next(
        fact["fact_id"] for fact in source["facts"] if fact["fact_type"] == "observation"
    )
    mutated = misattribute_result_to_patient(
        source,
        foreign_subject_ref="patient-foreign",
    )
    lifted = _lift_graph(mutated.graph)
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    scoped = classify_graph(source["facts"], lifted, policy=policy)
    assert scoped.faithful
    assert scoped.primary_endpoint_verdict == "INDETERMINATE"
    assert all(decision.classification != "MISATTRIBUTION" for decision in scoped.decisions)
    observation_decision = next(
        decision
        for decision in scoped.decisions
        if observation_id in decision.source_fact_ids
    )
    assert observation_decision.classification == "INDETERMINATE"
    assert observation_decision.primary_endpoint_eligible is False
    assert observation_decision.evidence.get("scope_note") == (
        "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
    )
    assert observation_decision.evidence.get("rationale_code") == (
        "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
    )

    development_diagnostic = classify_graph(source["facts"], lifted)
    assert not development_diagnostic.faithful
    assert any(
        decision.classification == "MISATTRIBUTION"
        for decision in development_diagnostic.decisions
    )


def test_fabrication_requires_and_cites_must_not_infer_rule() -> None:
    source = generate_lab_scenario("LAB-001", 9206)
    mutated = fabricate_observation(source)
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    result = classify_graph(source["facts"], _lift_graph(mutated.graph), policy=policy)

    fabrications = [
        decision for decision in result.decisions if decision.classification == "FABRICATION"
    ]
    assert fabrications
    assert not result.faithful
    assert fabrications[0].evidence["rule_ids"] == ["FREE_TEXT_INFERENCE_001"]


def test_unscored_fact_type_absence_is_indeterminate_not_omission() -> None:
    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    source = [
        {
            "fact_id": "encounter-1",
            "fact_type": "encounter",
            "subject_ref": "patient-1",
        }
    ]

    result = classify_graph(source, [], policy=policy)

    assert result.faithful
    assert result.primary_endpoint_verdict == "INDETERMINATE"
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.classification == "INDETERMINATE"
    assert decision.primary_endpoint_eligible is False
    assert decision.evidence["scope_note"] == (
        "NO_REQUIRED_PROJECTABILITY_RULE_FOR_WHOLE_FACT_ABSENCE"
    )


def test_may_lose_only_fact_absence_is_not_scored_as_omission() -> None:
    contract = {
        "contract": {"id": "TEST-MAY-LOSE", "version": "0.0.1"},
        "rules": [
            {
                "rule_id": "OBS_UNIT_LOSS",
                "canonical_fact": "observation.unit",
                "projectability": "MAY_LOSE",
            }
        ],
    }
    policy = compile_verification_policy(contract)
    source = generate_lab_scenario("LAB-001", 9207)
    observation = next(
        fact for fact in source["facts"] if fact["fact_type"] == "observation"
    )

    result = classify_graph([observation], [], policy=policy)

    assert result.faithful
    assert len(result.decisions) == 1
    assert result.decisions[0].classification == "INDETERMINATE"
    assert result.decisions[0].primary_endpoint_eligible is False


def test_contract_licensed_unit_conversion_uses_provider_jointly() -> None:
    source = generate_lab_scenario("LAB-001", 9210)
    target_graph = deepcopy(source)
    observation = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "observation"
    )
    source_observation = next(
        fact for fact in source["facts"] if fact["fact_type"] == "observation"
    )
    assert source_observation["unit"]["code"] == "mg/dL"
    observation["value"] = float(source_observation["value"]) * 0.01
    observation["unit"] = {
        "system": "http://unitsofmeasure.org",
        "code": "g/L",
        "display": "g/L",
    }

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))

    exact_baseline = classify_graph(
        source["facts"],
        _lift_graph(target_graph),
        policy=policy,
    )
    assert not exact_baseline.faithful
    assert exact_baseline.primary_endpoint_verdict == "UNFAITHFUL"

    provider_aware = classify_graph(
        source["facts"],
        _lift_graph(target_graph),
        policy=policy,
        unit_provider=_LabUnitProvider(),
    )

    assert provider_aware.faithful
    assert provider_aware.primary_endpoint_verdict == "FAITHFUL"
    decision = next(
        item
        for item in provider_aware.decisions
        if source_observation["fact_id"] in item.source_fact_ids
    )
    assert decision.classification == "LICENSED_NORMALIZATION"
    assert "UNIT_CONVERT" in decision.evidence["licensed_operations"]
    assert decision.evidence["ucum_checks"][0]["equivalent"] is True


def test_code_translation_requires_explicit_frozen_mapping_provider() -> None:
    source = generate_lab_scenario("LAB-001", 9211)
    target_graph = deepcopy(source)
    source_observation = next(
        fact for fact in source["facts"] if fact["fact_type"] == "observation"
    )
    target_observation = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "observation"
    )
    source_system = source_observation["concept"]["system"]
    source_code = source_observation["concept"]["code"]
    target_observation["concept"] = {
        "system": "urn:fhirbridge:test:local-lab",
        "code": "LOCAL-GLU",
        "display": source_observation["concept"]["display"],
        "local_code": "LOCAL-GLU",
    }

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    provider = FrozenMappingTerminologyEquivalence(
        {
            (
                source_system,
                source_code,
                "urn:fhirbridge:test:local-lab",
                "LOCAL-GLU",
            )
        },
        mapping_id="TEST-LAB-MAP",
        mapping_version="1.0.0",
    )

    exact_baseline = classify_graph(
        source["facts"],
        _lift_graph(target_graph),
        policy=policy,
    )
    assert not exact_baseline.faithful

    mapped = classify_graph(
        source["facts"],
        _lift_graph(target_graph),
        policy=policy,
        terminology_provider=provider,
    )

    assert mapped.faithful
    decision = next(
        item
        for item in mapped.decisions
        if source_observation["fact_id"] in item.source_fact_ids
    )
    assert decision.classification == "LICENSED_NORMALIZATION"
    assert "CODE_TRANSLATE" in decision.evidence["licensed_operations"]
    assert decision.evidence["terminology_checks"][0]["equivalent"] is True


def test_configured_equivalence_provider_failure_is_indeterminate_not_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 9212)
    target_graph = deepcopy(source)
    source_observation = next(
        fact for fact in source["facts"] if fact["fact_type"] == "observation"
    )
    target_observation = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "observation"
    )
    target_observation["value"] = float(source_observation["value"]) * 0.01
    target_observation["unit"] = {
        "system": "http://unitsofmeasure.org",
        "code": "g/L",
        "display": "g/L",
    }

    policy = compile_verification_policy(load_yaml(_CONTRACT_PATH))
    result = classify_graph(
        source["facts"],
        _lift_graph(target_graph),
        policy=policy,
        unit_provider=_UnavailableUnitProvider(),
    )

    decision = next(
        item
        for item in result.decisions
        if source_observation["fact_id"] in item.source_fact_ids
    )
    assert decision.classification == "INDETERMINATE"
    assert decision.primary_endpoint_eligible is False
    assert decision.evidence["rationale_code"] == "UNIT_PROVIDER_UNAVAILABLE"
    assert "RuntimeError" in decision.evidence["provider_error"]
    assert result.primary_endpoint_verdict == "INDETERMINATE"
