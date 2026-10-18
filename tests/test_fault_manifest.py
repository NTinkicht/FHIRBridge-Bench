import fhirbridge.artifact_faults
import fhirbridge.canonical
import fhirbridge.fault_manifest
import fhirbridge.faults
import fhirbridge.multi_faults
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _contract() -> dict:
    return fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)


def test_single_fault_manifest_records_reproducibility_fields() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 8301)
    mutant = fhirbridge.faults.corrupt_numeric_value(source, delta=11)

    manifest = fhirbridge.fault_manifest.manifest_for_seeded_fault(
        source,
        mutant.fault,
        contract=_contract(),
        mutation_operator="corrupt_numeric_value",
    ).to_dict()

    assert manifest["scenario_id"] == "LAB-001"
    assert manifest["graph_id"] == source["graph_id"]
    assert manifest["fault_id"] == "F002"
    assert manifest["mutation_level"] == "canonical"
    assert manifest["mutation_operator"] == "corrupt_numeric_value"
    assert manifest["expected_classifications"] == ("CORRUPTION",)
    assert manifest["expected_severity"] == "S3"
    assert manifest["structural_validity_expectation"] == "expected_valid"
    assert manifest["contract_id"] == "F2V-LAB-ORU-R01-001"
    assert manifest["contract_version"] == "0.2.0"
    assert manifest["affected_fact_ids"] == mutant.fault.affected_fact_ids
    assert len(manifest["manifest_sha256"]) == 64


def test_multi_fault_manifest_preserves_component_provenance() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-005", 8302)
    mutant = fhirbridge.multi_faults.omission_plus_fabricated_replacement(source)

    manifest = fhirbridge.fault_manifest.manifest_for_multi_fault(
        source,
        mutant.fault,
        contract=_contract(),
        mutation_operator="omission_plus_fabricated_replacement",
    ).to_dict()

    assert manifest["fault_id"] == "MF003"
    assert manifest["component_fault_ids"] == ("F008", "F001")
    assert manifest["expected_classifications"] == ("OMISSION", "FABRICATION")
    assert manifest["expected_severity"] == "S3"
    assert len(manifest["metadata"]["component_mutations"]) == 2


def test_artifact_fault_manifest_records_target_path_and_structural_expectation() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 8303)
    contract = _contract()
    artifact = fhirbridge.renderers.Hl7V251OruRendererA().render(
        source,
        contract=contract,
    ).artifact
    mutant = fhirbridge.artifact_faults.corrupt_message_version(artifact)

    manifest = fhirbridge.fault_manifest.manifest_for_artifact_fault(
        source,
        mutant,
        contract=contract,
        mutation_operator="corrupt_message_version",
    ).to_dict()

    assert manifest["fault_id"] == "F018"
    assert manifest["mutation_level"] == "artifact"
    assert manifest["expected_classifications"] == ("STRUCTURAL_ERROR",)
    assert manifest["structural_validity_expectation"] == "expected_invalid"
    assert manifest["target_paths"] == ("MSH-12",)


def test_fault_manifest_hash_is_deterministic() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 8304)
    mutant = fhirbridge.faults.corrupt_unit_without_conversion(source)

    first = fhirbridge.fault_manifest.manifest_for_seeded_fault(
        source,
        mutant.fault,
        contract=_contract(),
        mutation_operator="corrupt_unit_without_conversion",
    ).to_dict()
    second = fhirbridge.fault_manifest.manifest_for_seeded_fault(
        source,
        mutant.fault,
        contract=_contract(),
        mutation_operator="corrupt_unit_without_conversion",
    ).to_dict()

    assert first == second
    assert first["manifest_sha256"] == second["manifest_sha256"]
