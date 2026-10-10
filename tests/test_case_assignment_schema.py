from copy import deepcopy
from pathlib import Path

import yaml

from fhirbridge.schema_validation import load_yaml, validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (
    ROOT
    / "expert_validation"
    / "schema"
    / "case_assignment_manifest.schema.json"
)
TEMPLATE = (
    ROOT
    / "expert_validation"
    / "examples"
    / "case_assignment_manifest_template.yaml"
)


def _write_yaml(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_case_assignment_template_matches_schema() -> None:
    assert validate_document(TEMPLATE, SCHEMA) == []


def test_case_assignment_requires_exactly_two_distinct_reviewers(
    tmp_path: Path,
) -> None:
    document = deepcopy(load_yaml(TEMPLATE))
    document["assignments"][0]["primary_reviewer_ids"] = ["R1"]

    problems = validate_document(
        _write_yaml(tmp_path, "one-reviewer.yaml", document),
        SCHEMA,
    )

    assert problems


def test_case_assignment_rejects_opened_sealed_set(tmp_path: Path) -> None:
    document = deepcopy(load_yaml(TEMPLATE))
    document["sealed_set_opened"] = True

    problems = validate_document(
        _write_yaml(tmp_path, "opened.yaml", document),
        SCHEMA,
    )

    assert problems


def test_case_assignment_hashes_must_be_sha256(tmp_path: Path) -> None:
    document = deepcopy(load_yaml(TEMPLATE))
    document["reviewer_roster_sha256"] = "bad"

    problems = validate_document(
        _write_yaml(tmp_path, "bad-hash.yaml", document),
        SCHEMA,
    )

    assert problems
