from copy import deepcopy

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.faults import (
    corrupt_interpretation,
    corrupt_numeric_value,
    corrupt_observation_code,
    corrupt_patient_identifier,
    corrupt_reference_range,
    corrupt_result_status,
    corrupt_specimen_type,
    corrupt_unit_without_conversion,
    fabricate_observation,
    misattribute_result_to_patient,
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


def test_coded_result_value_code_is_compared_independently_of_display() -> None:
    source = generate_lab_scenario("LAB-004", 8105)
    target_graph = deepcopy(source)
    observation = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "observation"
    )
    observation["attributes"]["value_code"]["code"] = "POS"
    observation["attributes"]["value_code"]["display"] = "Positive"

    result = classify_graph(
        source["facts"],
        _target_with_representation_local_refs(target_graph),
    )

    assert any(
        decision.classification == "CORRUPTION"
        and decision.error_subtype == "terminology"
        and "value_code" in decision.evidence
        for decision in result.decisions
    )


def test_identifier_type_label_alone_is_not_a_fidelity_dimension() -> None:
    source = generate_lab_scenario("LAB-001", 8106)
    target_graph = deepcopy(source)
    for fact in target_graph["facts"]:
        for identifier in fact.get("identifiers", []):
            identifier["type"] = None

    result = classify_graph(
        source["facts"],
        _target_with_representation_local_refs(target_graph),
    )

    assert result.faithful
    assert not any(
        decision.classification == "CORRUPTION"
        and decision.error_subtype == "identifier"
        for decision in result.decisions
    )

def test_seeded_identifier_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8106)
    mutated = corrupt_patient_identifier(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "identifier"
        for d in result.decisions
    )


def test_seeded_temporal_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8107)
    mutated = shift_observation_time(source, minutes=45)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "temporal"
        for d in result.decisions
    )


def test_report_recorded_timestamp_is_part_of_semantic_fidelity() -> None:
    source = generate_lab_scenario("LAB-001", 8108)
    target_graph = deepcopy(source)
    report = next(
        fact for fact in target_graph["facts"] if fact["fact_type"] == "diagnostic_report"
    )
    report["temporal"]["recorded_at"] = "2026-01-15T19:00:00+00:00"

    result = classify_graph(
        source["facts"],
        _target_with_representation_local_refs(target_graph),
    )

    assert any(
        decision.classification == "CORRUPTION"
        and decision.error_subtype == "temporal"
        and "recorded_at" in decision.evidence
        for decision in result.decisions
    )


def test_seeded_status_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8109)
    mutated = corrupt_result_status(source, replacement_status="preliminary")

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION" and d.error_subtype == "status"
        for d in result.decisions
    )


def test_seeded_interpretation_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8110)
    mutated = corrupt_interpretation(source, replacement_code="H", replacement_display="High")

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION"
        and "interpretation" in d.evidence
        for d in result.decisions
    )


def test_seeded_reference_range_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-001", 8111)
    mutated = corrupt_reference_range(source, high_delta=15)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION"
        and "reference_range" in d.evidence
        for d in result.decisions
    )


def test_seeded_specimen_type_fault_is_classified_as_corruption() -> None:
    source = generate_lab_scenario("LAB-006", 8112)
    mutated = corrupt_specimen_type(source, replacement_type_label="whole_blood")

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert any(
        d.classification == "CORRUPTION"
        and d.error_subtype == "terminology"
        and "type_label" in d.evidence
        for d in result.decisions
    )


def test_seeded_omission_is_not_double_counted_as_fabrication() -> None:
    source = generate_lab_scenario("LAB-005", 8113)
    mutated = omit_required_observation(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert "OMISSION" in _classes(result)
    assert "FABRICATION" not in _classes(result)


def test_seeded_fabrication_is_detected_without_corrupting_supported_facts() -> None:
    source = generate_lab_scenario("LAB-001", 8114)
    mutated = fabricate_observation(source)

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert "FABRICATION" in _classes(result)
    assert "OMISSION" not in _classes(result)


def test_wrong_subject_has_misattribution_precedence() -> None:
    source = generate_lab_scenario("LAB-001", 8115)
    mutated = misattribute_result_to_patient(source, foreign_subject_ref="foreign-patient")

    result = classify_graph(source["facts"], _target_with_representation_local_refs(mutated.graph))

    assert "MISATTRIBUTION" in _classes(result)
    assert "FABRICATION" not in _classes(result)
    assert "OMISSION" not in _classes(result)
