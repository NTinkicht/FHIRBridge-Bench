from copy import deepcopy

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.faults import (
    corrupt_numeric_value,
    corrupt_observation_code,
    corrupt_patient_identifier,
    corrupt_unit_without_conversion,
    fabricate_observation,
    omit_required_observation,
    shift_observation_time,
)
from fhirbridge.verifier import LiftedFact, classify_graph


def _lift_graph(graph: dict) -> list[LiftedFact]:
    facts: list[LiftedFact] = []
    for fact in graph["facts"]:
        payload = deepcopy(fact)
        relationships = tuple(
            (relation["relation_type"], relation["target_fact_id"])
            for relation in fact.get("relations", [])
        )
        facts.append(
            LiftedFact(
                lifted_fact_id=f"lifted::{fact['fact_id']}",
                fact_type=fact["fact_type"],
                subject_ref=f"lifted::{fact['subject_ref']}" if fact.get("subject_ref") else None,
                semantic_payload=payload,
                target_paths=(f"fixture/{fact['fact_id']}",),
                relationships=tuple(
                    (relation_type, f"lifted::{target_id}")
                    for relation_type, target_id in relationships
                ),
            )
        )
    return facts


def _classes(result) -> list[str]:
    return [decision.classification for decision in result.decisions]


def _target_with_representation_local_refs(graph: dict) -> list[LiftedFact]:
    lifted = _lift_graph(graph)
    rewritten: list[LiftedFact] = []
    for fact in lifted:
        payload = deepcopy(fact.semantic_payload)
        payload["subject_ref"] = fact.subject_ref
        payload["relations"] = [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in fact.relationships
        ]
        rewritten.append(
            LiftedFact(
                lifted_fact_id=fact.lifted_fact_id,
                fact_type=fact.fact_type,
                subject_ref=fact.subject_ref,
                semantic_payload=payload,
                target_paths=fact.target_paths,
                relationships=fact.relationships,
            )
        )
    return rewritten


def test_clean_graph_is_semantically_faithful() -> None:
    source = generate_lab_scenario("LAB-001", 8101)
    target = _target_with_representation_local_refs(source)

    result = classify_graph(source["facts"], target)

    assert result.faithful
    assert set(_classes(result)) == {"VERIFIED_EQUIVALENT"}


def test_seeded_value_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8102)
    mutated = corrupt_numeric_value(source, delta=20)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    corruptions = [d for d in result.decisions if d.classification == "CORRUPTION"]
    assert not result.faithful
    assert any(d.error_subtype == "value" for d in corruptions)
    assert "OMISSION" not in _classes(result)


def test_seeded_unit_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8103)
    mutated = corrupt_unit_without_conversion(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "unit"
        for d in result.decisions
    )


def test_seeded_code_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8104)
    mutated = corrupt_observation_code(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "terminology"
        for d in result.decisions
    )


def test_seeded_identifier_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8105)
    mutated = corrupt_patient_identifier(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "identifier"
        for d in result.decisions
    )


def test_seeded_temporal_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8106)
    mutated = shift_observation_time(source, minutes=45)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "temporal"
        for d in result.decisions
    )


def test_seeded_omission_is_not_double_counted_as_fabrication() -> None:
    source = generate_lab_scenario("LAB-005", 8107)
    mutated = omit_required_observation(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert "OMISSION" in _classes(result)
    assert "FABRICATION" not in _classes(result)


def test_seeded_fabrication_is_detected_without_corrupting_supported_facts() -> None:
    source = generate_lab_scenario("LAB-001", 8108)
    mutated = fabricate_observation(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert "FABRICATION" in _classes(result)
    assert "OMISSION" not in _classes(result)


def test_wrong_subject_has_misattribution_precedence() -> None:
    source = generate_lab_scenario("LAB-001", 8109)
    target_graph = deepcopy(source)
    observation = next(f for f in target_graph["facts"] if f["fact_type"] == "observation")
    observation["subject_ref"] = "foreign-patient"

    result = classify_graph(source["facts"], _target_with_representation_local_refs(target_graph))

    assert "MISATTRIBUTION" in _classes(result)
    assert "FABRICATION" not in _classes(result)
