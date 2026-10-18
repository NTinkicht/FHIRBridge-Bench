import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

_BLIND_SCHEMA = Path("contracts/review/contract_review_blind_response.schema.json")
_UNBLINDED_SCHEMA = Path(
    "contracts/review/contract_review_unblinded_response.schema.json"
)


def _schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blind_response() -> dict:
    return {
        "schema_version": "0.2.0",
        "review_stage": "blind",
        "reviewer": {
            "reviewer_id": "R-EXT-001",
            "expertise": ["HL7 v2", "FHIR", "laboratory interfaces"],
            "review_date": "2026-10-10",
            "conflicts_of_interest": "None declared",
            "prior_project_involvement": "None",
            "lri_authoring_involvement": "None",
        },
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.3.0",
        },
        "rule_reviews": [
            {
                "rule_id": "ORDER_IDENTIFIER_MAPPING_001",
                "projectability_decision": "INDETERMINATE",
                "evidence_sufficient": "PARTLY",
                "evidence_references": ["LRI Edition 5 publication"],
                "main_concern": "Machine profile still pending.",
                "confidence": "MODERATE",
            }
        ],
        "attestation": {
            "independent_initial_classification": True,
            "no_model_outputs_used": True,
            "no_verifier_outputs_used": True,
            "no_renderer_outputs_used_as_correctness_evidence": True,
            "study_proposals_not_seen": True,
            "reviewer_did_not_author_project_rules": True,
            "not_universal_mapping_endorsement": True,
        },
    }


def _unblinded_response() -> dict:
    return {
        "schema_version": "0.2.0",
        "review_stage": "unblinded",
        "blind_response_sha256": "a" * 64,
        "reviewer_id": "R-EXT-001",
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.3.0",
        },
        "rule_reviews": [
            {
                "rule_id": "ORDER_IDENTIFIER_MAPPING_001",
                "target_locus_defensible": "PARTLY",
                "alternative_target_loci": ["ORC-3", "OBR-3"],
                "accepted_operations": ["COPY"],
                "rejected_operations": ["NORMALIZE"],
                "equivalence_adequate": "INDETERMINATE",
                "severity_plausible": "YES",
                "proposal_comment": "Retain field-locus ambiguity until bundle review.",
            }
        ],
        "attestation": {
            "blind_response_locked_before_proposal_disclosure": True,
            "blind_response_not_replaced": True,
        },
    }


def test_blind_stage_schema_accepts_independent_classification() -> None:
    jsonschema.Draft202012Validator(_schema(_BLIND_SCHEMA)).validate(
        _blind_response()
    )


def test_blind_stage_schema_rejects_proposal_aware_fields() -> None:
    response = _blind_response()
    response["rule_reviews"][0]["target_locus_defensible"] = "YES"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(_BLIND_SCHEMA)).validate(
            response
        )


def test_blind_stage_schema_requires_proposal_blinding_attestation() -> None:
    response = _blind_response()
    response["attestation"]["study_proposals_not_seen"] = False

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(_BLIND_SCHEMA)).validate(
            response
        )


def test_unblinded_stage_schema_requires_locked_blind_response_hash() -> None:
    response = _unblinded_response()
    del response["blind_response_sha256"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(_UNBLINDED_SCHEMA)).validate(
            response
        )


def test_unblinded_stage_schema_accepts_proposal_critique() -> None:
    response = deepcopy(_unblinded_response())

    jsonschema.Draft202012Validator(_schema(_UNBLINDED_SCHEMA)).validate(
        response
    )
