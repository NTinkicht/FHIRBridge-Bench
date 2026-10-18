from pathlib import Path

from fhirbridge.schema_validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA = ROOT / "contracts" / "schema" / "projectability_contract.schema.yaml"


def test_lab_oru_r01_contract_v02_matches_schema() -> None:
    problems = validate_document(
        ROOT / "contracts" / "fhir_to_v2" / "lab_oru_r01_v0.2.yaml",
        CONTRACT_SCHEMA,
    )
    assert problems == []
