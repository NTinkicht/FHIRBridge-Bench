from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.multi_faults import (
    omission_plus_fabricated_replacement,
    patient_swap_plus_valid_result,
    value_plus_unit_joint_corruption,
)


def _observations(graph: dict) -> list[dict]:
    return [fact for fact in graph["facts"] if fact["fact_type"] == "observation"]


def test_mf001_joint_value_unit_corruption_tracks_both_components() -> None:
    original = generate_lab_scenario("LAB-001", 8101)
    mutant = value_plus_unit_joint_corruption(
        original,
        value_delta=7,
        replacement_unit="mmol/L",
    )

    before = _observations(original)[0]
    after = _observations(mutant.graph)[0]

    assert mutant.fault.fault_id == "MF001"
    assert tuple(component.fault_id for component in mutant.fault.components) == (
        "F002",
        "F003",
    )
    assert mutant.fault.expected_resolution == ("CORRUPTION",)
    assert after["value"] == before["value"] + 7
    assert after["unit"] != before["unit"]
    assert original != mutant.graph


def test_mf002_patient_swap_preserves_result_content() -> None:
    original = generate_lab_scenario("LAB-001", 8102)
    mutant = patient_swap_plus_valid_result(
        original,
        foreign_subject_ref="patient-foreign-mf002",
    )

    before = _observations(original)[0]
    after = _observations(mutant.graph)[0]

    assert mutant.fault.fault_id == "MF002"
    assert tuple(component.fault_id for component in mutant.fault.components) == ("F006",)
    assert mutant.fault.expected_resolution == ("MISATTRIBUTION",)
    assert after["subject_ref"] == "patient-foreign-mf002"
    assert after["concept"] == before["concept"]
    assert after["value"] == before["value"]


def test_mf003_omission_plus_fabrication_keeps_count_but_changes_identity() -> None:
    original = generate_lab_scenario("LAB-005", 8103)
    mutant = omission_plus_fabricated_replacement(original)

    original_ids = {fact["fact_id"] for fact in _observations(original)}
    mutant_ids = {fact["fact_id"] for fact in _observations(mutant.graph)}
    omitted_id = mutant.fault.components[0].affected_fact_ids[0]
    fabricated_id = mutant.fault.components[1].affected_fact_ids[0]

    assert mutant.fault.fault_id == "MF003"
    assert tuple(component.fault_id for component in mutant.fault.components) == (
        "F008",
        "F001",
    )
    assert mutant.fault.expected_resolution == ("OMISSION", "FABRICATION")
    assert len(mutant_ids) == len(original_ids)
    assert omitted_id in original_ids
    assert omitted_id not in mutant_ids
    assert fabricated_id not in original_ids
    assert fabricated_id in mutant_ids


def test_multi_fault_operators_do_not_mutate_original_graph() -> None:
    original = generate_lab_scenario("LAB-005", 8104)
    snapshot = generate_lab_scenario("LAB-005", 8104)

    _ = value_plus_unit_joint_corruption(original)
    _ = patient_swap_plus_valid_result(original)
    _ = omission_plus_fabricated_replacement(original)

    assert original == snapshot
