"""Deterministic schema validation helpers for research artifacts.

This module deliberately contains no HL7/FHIR transformation logic. It exists
so protocol artifacts can fail fast in CI before they become inputs to the
measurement study.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


@dataclass(frozen=True)
class SchemaProblem:
    """One normalized schema-validation problem."""

    path: str
    message: str
    validator: str | None

    def __str__(self) -> str:
        where = self.path or "<root>"
        return f"{where}: {self.message}"


class ArtifactValidationError(ValueError):
    """Raised when a research artifact does not satisfy its frozen schema."""

    def __init__(self, artifact: Path, problems: list[SchemaProblem]) -> None:
        self.artifact = artifact
        self.problems = problems
        rendered = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(f"{artifact} failed schema validation:\n{rendered}")


def load_yaml(path: str | Path) -> Any:
    """Load a YAML document using the safe loader."""

    document_path = Path(path)
    with document_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _schema_resource(schema: dict[str, Any]) -> Resource[Any]:
    return Resource.from_contents(schema, default_specification=DRAFT202012)


def build_registry(schema_directories: Iterable[str | Path]) -> Registry[Any]:
    """Build a local registry for schemas carrying stable ``$id`` values.

    Remote retrieval is intentionally not enabled. A validation run should be
    reproducible from the repository checkout rather than silently depending on
    mutable network resources.
    """

    registry: Registry[Any] = Registry()
    seen_ids: set[str] = set()

    for directory in schema_directories:
        schema_dir = Path(directory)
        if not schema_dir.exists():
            continue
        for schema_path in sorted(schema_dir.glob("*.y*ml")):
            schema = load_yaml(schema_path)
            if not isinstance(schema, dict):
                continue
            schema_id = schema.get("$id")
            if not schema_id:
                continue
            if schema_id in seen_ids:
                raise ValueError(f"duplicate schema $id {schema_id!r}: {schema_path}")
            registry = registry.with_resource(schema_id, _schema_resource(schema))
            seen_ids.add(schema_id)

    return registry


def _normalized_problem(error: ValidationError) -> SchemaProblem:
    path = ".".join(str(part) for part in error.absolute_path)
    return SchemaProblem(
        path=path,
        message=error.message,
        validator=str(error.validator) if error.validator is not None else None,
    )


def validate_document(
    artifact_path: str | Path,
    schema_path: str | Path,
    *,
    extra_schema_directories: Iterable[str | Path] = (),
) -> list[SchemaProblem]:
    """Validate one YAML artifact and return all normalized problems.

    An empty list means the artifact is valid. This non-throwing form is useful
    for CI reports and batch validation.
    """

    artifact = Path(artifact_path)
    schema_file = Path(schema_path)
    instance = load_yaml(artifact)
    schema = load_yaml(schema_file)

    if not isinstance(schema, dict):
        raise TypeError(f"schema must be a mapping: {schema_file}")

    directories = [schema_file.parent, *map(Path, extra_schema_directories)]
    registry = build_registry(directories)
    validator = Draft202012Validator(schema, registry=registry)

    errors = sorted(
        validator.iter_errors(instance),
        key=lambda err: tuple(str(item) for item in err.absolute_path),
    )
    return [_normalized_problem(error) for error in errors]


def require_valid_document(
    artifact_path: str | Path,
    schema_path: str | Path,
    *,
    extra_schema_directories: Iterable[str | Path] = (),
) -> None:
    """Validate one artifact and raise ``ArtifactValidationError`` on failure."""

    artifact = Path(artifact_path)
    problems = validate_document(
        artifact,
        schema_path,
        extra_schema_directories=extra_schema_directories,
    )
    if problems:
        raise ArtifactValidationError(artifact, problems)
