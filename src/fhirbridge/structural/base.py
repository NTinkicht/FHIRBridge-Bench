"""Structural-validation interfaces kept separate from semantic verification.

A structural validator answers whether an artifact satisfies a declared syntax or
profile gate. It must not infer semantic fidelity from conformance success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StructuralFinding:
    code: str
    message: str
    severity: str
    path: str | None = None


@dataclass(frozen=True)
class StructuralValidationResult:
    valid: bool
    validator_id: str
    validator_version: str
    profile: str
    findings: tuple[StructuralFinding, ...] = ()
    metadata: dict[str, object] | None = None


class StructuralValidator(Protocol):
    @property
    def validator_id(self) -> str: ...

    @property
    def validator_version(self) -> str: ...

    def validate(self, artifact: str) -> StructuralValidationResult: ...
