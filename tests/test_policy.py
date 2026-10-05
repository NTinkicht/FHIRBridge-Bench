from copy import deepcopy

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.schema_validation import load_yaml
from fhirbridge.verifier import LiftedFact, classify_graph, compile_verification_policy

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


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
    assert all(decision.classification == "VERIFIED_EQUIVALENT" for decision in result.decisions)


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
