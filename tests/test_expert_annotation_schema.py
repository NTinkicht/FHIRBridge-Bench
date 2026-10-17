import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_PATH = Path("expert_validation/schema/expert_annotation.schema.json")


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_annotation() -> dict:
    return {
        "schema_version": "0.1.0",
        "case_id": "CASE-001",
        "stage": "SEALED",
        "reviewer": {
            "reviewer_id": "REV-A",
            "review_date": "2026-10-05",
        },
        "artifacts": {
            "source_id": "SRC-001",
            "source_sha256": "a" * 64,
            "target_id": "TGT-001",
            "target_sha256": "b" * 64,
        },
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.2.0",
        },
        "transformation_verdict": {
            "major_semantic_error": "YES",
            "confidence": "HIGH",
            "comment": "Required observation was omitted.",
        },
        "fact_annotations": [
            {
                "annotation_id": "ANN-001",
                "fact_id": "obs-001",
                "source_evidence": ["Observation.valueQuantity"],
                "target_evidence": [],
                "contract_rule_ids": ["OBSERVATION_VALUE_001"],
                "error_class": "OMISSION",
                "severity": "S2",
                "confidence": "HIGH",
                "comment": "No target representation found.",
            }
        ],
        "blinding_attestation": {
            "model_identity_hidden": True,
            "strategy_hidden": True,
            "verifier_output_hidden": True,
            "claimed_provenance_hidden": True,
            "other_reviewer_labels_hidden": True,
        },
    }


def test_valid_blinded_expert_annotation_conforms_to_schema() -> None:
    jsonschema.Draft202012Validator(_schema()).validate(_valid_annotation())


def test_corruption_requires_subtype() -> None:
    annotation = _valid_annotation()
    fact = annotation["fact_annotations"][0]
    fact["error_class"] = "CORRUPTION"
    fact.pop("corruption_subtype", None)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(annotation)


def test_schema_rejects_broken_blinding_attestation() -> None:
    annotation = _valid_annotation()
    annotation["blinding_attestation"]["verifier_output_hidden"] = False

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(annotation)


def test_schema_rejects_invalid_artifact_hash() -> None:
    annotation = _valid_annotation()
    annotation["artifacts"]["source_sha256"] = "not-a-sha"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(annotation)
