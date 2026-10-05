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


def _observation_count(graph: dict) -> int:
    return sum(fact["fact_type"] == "observation" for fact in graph["facts"])


def test_value_corruption_changes_only_selected_value_semantics() -> None:
    original = generate_lab_scenario("LAB-001", 7001)
    mutated = corrupt_numeric_value(original, delta=10)

    assert mutated.fault.fault_id == "F002"
    assert mutated.fault.expected_class == "CORRUPTION"
    assert original != mutated.graph
    source_value = next(
        fact["value"] for fact in original["facts"] if fact["fact_type"] == "observation"
    )
    target_value = next(
        fact["value"] for fact in mutated.graph["facts"] if fact["fact_type"] == "observation"
    )
    assert target_value == source_value + 10


def test_unit_corruption_does_not_change_numeric_value() -> None:
    original = generate_lab_scenario("LAB-001", 7002)
    mutated = corrupt_unit_without_conversion(original)

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["value"] == before["value"]
    assert after["unit"] != before["unit"]
    assert mutated.fault.fault_id == "F003"


def test_code_corruption_changes_concept_not_value() -> None:
    original = generate_lab_scenario("LAB-001", 7003)
    mutated = corrupt_observation_code(original)

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["value"] == before["value"]
    assert after["concept"] != before["concept"]
    assert mutated.fault.fault_id == "F004"


def test_patient_identifier_corruption_preserves_namespace() -> None:
    original = generate_lab_scenario("LAB-001", 7004)
    mutated = corrupt_patient_identifier(original)

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "patient_identity")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "patient_identity")
    assert after["identifiers"][0]["system"] == before["identifiers"][0]["system"]
    assert after["identifiers"][0]["value"] != before["identifiers"][0]["value"]
    assert mutated.fault.fault_id == "F005"


def test_patient_result_misattribution_changes_only_subject_reference() -> None:
    original = generate_lab_scenario("LAB-001", 7005)
    mutated = misattribute_result_to_patient(original, foreign_subject_ref="patient-foreign")

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["subject_ref"] == "patient-foreign"
    assert after["concept"] == before["concept"]
    assert after["value"] == before["value"]
    assert mutated.fault.fault_id == "F006"
    assert mutated.fault.expected_class == "MISATTRIBUTION"


def test_omission_removes_observation_and_dangling_relations() -> None:
    original = generate_lab_scenario("LAB-005", 7006)
    mutated = omit_required_observation(original)

    assert _observation_count(mutated.graph) == _observation_count(original) - 1
    removed = mutated.fault.affected_fact_ids[0]
    for fact in mutated.graph["facts"]:
        assert all(
            relation.get("target_fact_id") != removed
            for relation in fact.get("relations", [])
        )
    assert mutated.fault.fault_id == "F008"


def test_temporal_corruption_preserves_iso_timestamp_shape() -> None:
    original = generate_lab_scenario("LAB-001", 7007)
    mutated = shift_observation_time(original, minutes=60)

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["temporal"]["effective_start"] != before["temporal"]["effective_start"]
    assert "T" in after["temporal"]["effective_start"]
    assert mutated.fault.fault_id == "F010"


def test_status_corruption_preserves_result_value() -> None:
    original = generate_lab_scenario("LAB-001", 7008)
    mutated = corrupt_result_status(original, replacement_status="preliminary")

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["value"] == before["value"]
    assert after["attributes"]["status"] == "preliminary"
    assert mutated.fault.fault_id == "F011"


def test_interpretation_corruption_preserves_result_value_and_range() -> None:
    original = generate_lab_scenario("LAB-001", 7009)
    mutated = corrupt_interpretation(original, replacement_code="H", replacement_display="High")

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["value"] == before["value"]
    assert after["attributes"]["reference_range"] == before["attributes"]["reference_range"]
    assert after["attributes"]["interpretation"] != before["attributes"]["interpretation"]
    assert mutated.fault.fault_id == "F012"


def test_reference_range_corruption_preserves_result_and_interpretation() -> None:
    original = generate_lab_scenario("LAB-001", 7010)
    mutated = corrupt_reference_range(original, high_delta=30)

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "observation")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "observation")
    assert after["value"] == before["value"]
    assert after["attributes"]["interpretation"] == before["attributes"]["interpretation"]
    assert after["attributes"]["reference_range"] != before["attributes"]["reference_range"]
    assert mutated.fault.fault_id == "F013"


def test_specimen_type_corruption_preserves_specimen_identifier() -> None:
    original = generate_lab_scenario("LAB-006", 7011)
    mutated = corrupt_specimen_type(original, replacement_type_label="whole_blood")

    before = next(fact for fact in original["facts"] if fact["fact_type"] == "specimen")
    after = next(fact for fact in mutated.graph["facts"] if fact["fact_type"] == "specimen")
    assert after["identifiers"] == before["identifiers"]
    assert after["attributes"]["type_label"] == "whole_blood"
    assert after["attributes"]["type_label"] != before["attributes"]["type_label"]
    assert mutated.fault.fault_id == "F015"


def test_fabrication_adds_one_unsupported_observation() -> None:
    original = generate_lab_scenario("LAB-001", 7012)
    mutated = fabricate_observation(original)

    assert _observation_count(mutated.graph) == _observation_count(original) + 1
    fabricated_id = mutated.fault.affected_fact_ids[0]
    assert any(fact["fact_id"] == fabricated_id for fact in mutated.graph["facts"])
    assert mutated.fault.fault_id == "F001"
    assert mutated.fault.expected_class == "FABRICATION"


def test_fault_operators_do_not_mutate_original_graph() -> None:
    original = generate_lab_scenario("LAB-006", 7013)
    snapshot = generate_lab_scenario("LAB-006", 7013)

    _ = corrupt_numeric_value(original)
    _ = corrupt_unit_without_conversion(original)
    _ = misattribute_result_to_patient(original)
    _ = omit_required_observation(original)
    _ = corrupt_result_status(original)
    _ = corrupt_interpretation(original)
    _ = corrupt_reference_range(original)
    _ = corrupt_specimen_type(original)
    _ = fabricate_observation(original)

    assert original == snapshot
