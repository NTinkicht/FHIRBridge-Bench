from copy import deepcopy
from pathlib import Path

import yaml

from fhirbridge.schema_validation import load_yaml, validate_document

ROOT = Path(__file__).resolve().parents[1]
DECLARATION_SCHEMA = (
    ROOT / "renderer_validation" / "schema" / "renderer_implementation_declaration.schema.json"
)
DISAGREEMENT_SCHEMA = (
    ROOT / "renderer_validation" / "schema" / "renderer_disagreement.schema.json"
)
DECLARATION_EXAMPLE = (
    ROOT / "renderer_validation" / "examples" / "renderer_b_declaration_template.yaml"
)
DISAGREEMENT_EXAMPLE = (
    ROOT / "renderer_validation" / "examples" / "renderer_disagreement_example.yaml"
)


def _write_yaml(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_renderer_b_declaration_template_matches_schema() -> None:
    assert validate_document(DECLARATION_EXAMPLE, DECLARATION_SCHEMA) == []


def test_renderer_disagreement_example_matches_schema() -> None:
    assert validate_document(DISAGREEMENT_EXAMPLE, DISAGREEMENT_SCHEMA) == []


def test_declaration_requires_explicit_renderer_a_exposure_fields(tmp_path: Path) -> None:
    declaration = deepcopy(load_yaml(DECLARATION_EXAMPLE))
    del declaration["independence"]["renderer_a_outputs_inspected_before_initial_commit"]

    problems = validate_document(
        _write_yaml(tmp_path, "missing-exposure-field.yaml", declaration),
        DECLARATION_SCHEMA,
    )

    assert problems
    assert any(
        "renderer_a_outputs_inspected_before_initial_commit" in problem.message
        for problem in problems
    )


def test_declaration_source_commit_must_be_git_like_hash(tmp_path: Path) -> None:
    declaration = deepcopy(load_yaml(DECLARATION_EXAMPLE))
    declaration["implementation"]["source_commit"] = "not-a-commit"

    problems = validate_document(
        _write_yaml(tmp_path, "invalid-commit.yaml", declaration),
        DECLARATION_SCHEMA,
    )

    assert problems


def test_disagreement_classification_must_use_frozen_vocabulary(tmp_path: Path) -> None:
    disagreement = deepcopy(load_yaml(DISAGREEMENT_EXAMPLE))
    disagreement["classification"] = "MAJORITY_VOTE"

    problems = validate_document(
        _write_yaml(tmp_path, "invalid-classification.yaml", disagreement),
        DISAGREEMENT_SCHEMA,
    )

    assert problems
    assert any("MAJORITY_VOTE" in problem.message for problem in problems)


def test_external_comparator_cannot_be_declared_ground_truth(tmp_path: Path) -> None:
    disagreement = deepcopy(load_yaml(DISAGREEMENT_EXAMPLE))
    disagreement["external_comparator"] = {
        "name": "example converter",
        "version": "1.0",
        "observation": "comparison only",
        "used_as_ground_truth": True,
    }

    problems = validate_document(
        _write_yaml(tmp_path, "invalid-oracle.yaml", disagreement),
        DISAGREEMENT_SCHEMA,
    )

    assert problems
    assert any("False" in problem.message for problem in problems)
