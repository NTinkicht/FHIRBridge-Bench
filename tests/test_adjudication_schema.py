import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_PATH = Path("expert_validation/schema/adjudication.schema.json")


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_record() -> dict:
    return {
        "schema_version": "0.1.0",
        "case_id": "CASE-001",
        "primary_reviews": [
            {
                "reviewer_id": "REV-A",
                "annotation_sha256": "a" * 64,
                "major_semantic_error": "NO",
            },
            {
                "reviewer_id": "REV-B",
                "annotation_sha256": "b" * 64,
                "major_semantic_error": "YES",
            },
        ],
        "adjudicator": {
            "reviewer_id": "REV-C",
            "review_date": "2026-10-05",
        },
        "adjudicated_verdict": "YES",
        "rationale": "A required laboratory observation is absent from the target.",
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.2.0",
        },
        "post_label_reference_used": False,
    }


def test_valid_adjudication_record_conforms_to_schema() -> None:
    jsonschema.Draft202012Validator(_schema()).validate(_valid_record())


def test_adjudication_requires_exactly_two_primary_reviews() -> None:
    record = _valid_record()
    record["primary_reviews"] = record["primary_reviews"][:1]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(record)


def test_adjudication_preserves_primary_review_hashes() -> None:
    record = _valid_record()
    record["primary_reviews"][0]["annotation_sha256"] = "bad-hash"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(record)


def test_indeterminate_adjudication_is_allowed() -> None:
    record = _valid_record()
    record["adjudicated_verdict"] = "INDETERMINATE"

    jsonschema.Draft202012Validator(_schema()).validate(record)
