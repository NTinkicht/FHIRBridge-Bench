import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_PATH = Path("contracts/review/contract_review_response.schema.json")


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_response() -> dict:
    return {
        "schema_version": "0.1.0",
        "reviewer": {
            "reviewer_id": "R-EXT-001",
            "expertise": ["HL7 v2", "FHIR", "laboratory interfaces"],
            "review_date": "2026-10-05",
            "conflicts_of_interest": "None declared",
        },
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.2.0",
        },
        "rule_reviews": [
            {
                "rule_id": "OBSERVATION_VALUE_001",
                "projectability_decision": "MUST_PRESERVE",
                "target_locus_defensible": "YES",
                "alternative_target_loci": [],
                "accepted_operations": ["COPY", "NORMALIZE", "UNIT_CONVERT"],
                "rejected_operations": [],
                "rejected_operation_reasons": {},
                "equivalence_adequate": "YES",
                "severity_plausible": "YES",
                "evidence_sufficient": "YES",
                "evidence_references": [
                    "HL7 v2-to-FHIR STU1 OBX to Observation mapping"
                ],
                "main_concern": "",
                "confidence": "HIGH",
            }
        ],
        "attestation": {
            "independent_initial_classification": True,
            "no_model_outputs_used": True,
            "no_verifier_outputs_used": True,
            "not_universal_mapping_endorsement": True,
        },
    }


def test_valid_external_review_response_conforms_to_schema() -> None:
    jsonschema.Draft202012Validator(_schema()).validate(_valid_response())


def test_schema_rejects_unrecognized_projectability_label() -> None:
    response = _valid_response()
    response["rule_reviews"][0]["projectability_decision"] = "PRESERVE_IF_POSSIBLE"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(response)


def test_schema_requires_independence_attestation() -> None:
    response = _valid_response()
    response["attestation"]["no_model_outputs_used"] = False

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(response)


def test_schema_pins_contract_identity_and_version() -> None:
    response = _valid_response()
    response["contract"]["version"] = "0.3.0"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(response)
