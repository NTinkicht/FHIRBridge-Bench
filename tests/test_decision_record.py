from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.faults import fabricate_observation
from fhirbridge.schema_validation import load_yaml, validate_document
from fhirbridge.verifier import LiftedFact, SemanticDecision, classify_graph, compile_verification_policy
from fhirbridge.verifier.decision_record import emit_semantic_decision_record

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "fhir_to_v2" / "lab_oru_r01_v0.2.yaml"
DECISION_SCHEMA = ROOT / "verifier" / "schema" / "semantic_decision.schema.yaml"


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


def _validate_record(tmp_path: Path, record: dict) -> None:
    path = tmp_path / "decision.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    problems = validate_document(path, DECISION_SCHEMA)
    assert problems == []


def _policy():
    return compile_verification_policy(load_yaml(CONTRACT_PATH))


def _observation_decision(result, classification: str):
    return next(
        decision
        for decision in result.decisions
        if decision.classification == classification
        and decision.source_fact_ids
        and decision.source_fact_ids[0].startswith("observation-")
    )


def test_verified_observation_emits_exact_fact_rule_union(tmp_path: Path) -> None:
    source = generate_lab_scenario("LAB-001", 9301)
    lifted = _lift_graph(source)
    policy = _policy()
    result = classify_graph(source["facts"], lifted, policy=policy)
    decision = _observation_decision(result, "VERIFIED_EQUIVALENT")

    record = emit_semantic_decision_record(
        decision,
        policy=policy,
        source_facts=source["facts"],
        target_facts=lifted,
        structural_validation_ref="STRUCT-LAB-001",
    )

    source_fact = next(
        fact for fact in source["facts"] if fact["fact_id"] == decision.source_fact_ids[0]
    )
    expected_rule_ids = list(policy.by_fact_type[source_fact["fact_type"]].rule_ids)
    assert record["contract"]["rule_ids"] == expected_rule_ids
    assert record["contract"]["rule_ids"]
    assert record["target_paths"]
    assert record["evidence"]["structural_validation_ref"] == "STRUCT-LAB-001"
    _validate_record(tmp_path, record)


def test_value_corruption_emits_only_value_rule_ids(tmp_path: Path) -> None:
    source = generate_lab_scenario("LAB-001", 9302)
    mutated = deepcopy(source)
    observation = next(
        fact for fact in mutated["facts"] if fact["fact_type"] == "observation"
    )
    assert observation["value"] is not None
    observation["value"] = observation["value"] + 7

    lifted = _lift_graph(mutated)
    policy = _policy()
    result = classify_graph(source["facts"], lifted, policy=policy)
    decision = _observation_decision(result, "CORRUPTION")

    record = emit_semantic_decision_record(
        decision,
        policy=policy,
        source_facts=source["facts"],
        target_facts=lifted,
    )

    assert record["error_subtype"] == "value"
    assert record["contract"]["rule_ids"] == list(
        policy.rules_for_field("observation", "value")
    )
    assert "value" in record["evidence"]["decision_details"]
    _validate_record(tmp_path, record)


def test_required_field_omission_emits_omitted_field_rule_ids(tmp_path: Path) -> None:
    source = generate_lab_scenario("LAB-001", 9303)
    mutated = deepcopy(source)
    observation = next(
        fact for fact in mutated["facts"] if fact["fact_type"] == "observation"
    )
    observation["value"] = None

    lifted = _lift_graph(mutated)
    policy = _policy()
    result = classify_graph(source["facts"], lifted, policy=policy)
    decision = _observation_decision(result, "OMISSION")

    record = emit_semantic_decision_record(
        decision,
        policy=policy,
        source_facts=source["facts"],
        target_facts=lifted,
    )

    assert record["contract"]["rule_ids"] == list(
        policy.rules_for_field("observation", "value")
    )
    assert record["evidence"]["decision_details"]["omitted_field"] == "value"
    _validate_record(tmp_path, record)


def test_fabrication_emits_explicit_must_not_infer_rule_ids(tmp_path: Path) -> None:
    source = generate_lab_scenario("LAB-001", 9304)
    mutated = fabricate_observation(source)
    lifted = _lift_graph(mutated.graph)
    policy = _policy()
    result = classify_graph(source["facts"], lifted, policy=policy)
    decision = next(
        item for item in result.decisions if item.classification == "FABRICATION"
    )

    record = emit_semantic_decision_record(
        decision,
        policy=policy,
        source_facts=source["facts"],
        target_facts=lifted,
    )

    assert record["contract"]["rule_ids"] == list(policy.must_not_infer_rule_ids)
    assert record["contract"]["rule_ids"] == ["FREE_TEXT_INFERENCE_001"]
    assert record["source_payload"] is None
    assert record["target_payload"] is not None
    _validate_record(tmp_path, record)


def test_nonendpoint_indeterminate_may_emit_empty_rule_ids(tmp_path: Path) -> None:
    policy = _policy()
    decision = SemanticDecision(
        decision_id="diagnostic-out-of-scope",
        classification="INDETERMINATE",
        primary_endpoint_eligible=False,
        evidence={"rationale_code": "OUTSIDE_FROZEN_SCOPE"},
    )

    record = emit_semantic_decision_record(
        decision,
        policy=policy,
        source_facts=[],
        target_facts=[],
    )

    assert record["contract"]["rule_ids"] == []
    _validate_record(tmp_path, record)


def test_endpoint_decision_without_governing_rule_fails_loudly() -> None:
    policy = _policy()
    source = {
        "fact_id": "encounter-unsupported",
        "fact_type": "encounter",
    }
    decision = SemanticDecision(
        decision_id="encounter-unsupported:verified",
        classification="VERIFIED_EQUIVALENT",
        source_fact_ids=(source["fact_id"],),
        evidence={"rationale_code": "FACT_SEMANTICS_PRESERVED"},
    )

    with pytest.raises(ValueError, match="no exact governing contract rule IDs"):
        emit_semantic_decision_record(
            decision,
            policy=policy,
            source_facts=[source],
            target_facts=[],
        )
