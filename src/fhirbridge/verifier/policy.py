"""Compile a projectability contract into verifier comparison policy.

The semantic verifier must not silently score canonical properties that the
frozen contract does not declare projectable. This module converts the
machine-readable contract into a compact, standard-independent field policy.

The policy is intentionally conservative: unknown canonical facts are ignored
rather than inferred into scope. A missing rule therefore cannot accidentally
become a confirmatory endpoint merely because both reference renderers happen
to preserve the same implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FactComparisonPolicy:
    """Fields and projectability classes scored for one canonical fact type."""

    fact_type: str
    fields: frozenset[str]
    rule_ids: tuple[str, ...]
    field_projectability: dict[str, str]

    def scores(self, field: str) -> bool:
        return field in self.fields

    def projectability(self, field: str) -> str | None:
        return self.field_projectability.get(field)


@dataclass(frozen=True)
class VerificationPolicy:
    """Contract-derived semantic comparison policy."""

    contract_id: str
    contract_version: str
    by_fact_type: dict[str, FactComparisonPolicy]

    def scores(self, fact_type: str, field: str) -> bool:
        policy = self.by_fact_type.get(fact_type)
        return policy is not None and policy.scores(field)

    def projectability(self, fact_type: str, field: str) -> str | None:
        policy = self.by_fact_type.get(fact_type)
        if policy is None:
            return None
        return policy.projectability(field)


_CANONICAL_FIELD_MAP: dict[str, tuple[str, tuple[str, ...]]] = {
    "patient.identifier": ("patient_identity", ("identifiers",)),
    "patient.name": ("patient_identity", ("attributes.name",)),
    "patient.birthDate": (
        "patient_identity",
        ("temporal.effective_start", "attributes.birthDate"),
    ),
    "report.code": ("diagnostic_report", ("concept",)),
    "report.effective": ("diagnostic_report", ("temporal.effective_start",)),
    "report.issued": ("diagnostic_report", ("temporal.recorded_at",)),
    "report.status": ("diagnostic_report", ("attributes.status",)),
    "observation.code": ("observation", ("concept",)),
    "observation.value": ("observation", ("value", "attributes.value_code")),
    "observation.unit": ("observation", ("unit",)),
    "observation.referenceRange": ("observation", ("attributes.reference_range",)),
    "observation.interpretation": ("observation", ("attributes.interpretation",)),
    "observation.status": ("observation", ("attributes.status",)),
    "observation.effective": ("observation", ("temporal.effective_start",)),
    "specimen.identifier": ("specimen", ("identifiers",)),
    "specimen.type": ("specimen", ("attributes.type_label",)),
    "specimen.collection.method": (
        "specimen",
        ("attributes.collection_method_label",),
    ),
    "specimen.collection.quantity": (
        "specimen",
        ("attributes.collection_quantity",),
    ),
    "specimen.collection.time": ("specimen", ("temporal.effective_start",)),
}


def compile_verification_policy(contract: dict[str, Any]) -> VerificationPolicy:
    """Compile supported contract rules into a comparison policy.

    Rules classified as ``INDETERMINATE`` are excluded from confirmatory
    scoring. ``MUST_NOT_INFER`` rules govern unsupported additions and therefore
    do not introduce source fields to compare. The projectability class is kept
    per canonical field so later classification can distinguish required-field
    omission from ordinary semantic mutation without consulting renderer logic.
    """

    header = contract.get("contract", {})
    fields_by_type: dict[str, set[str]] = {}
    rules_by_type: dict[str, list[str]] = {}
    projectability_by_type: dict[str, dict[str, str]] = {}

    rules = contract.get("rules", [])
    if not isinstance(rules, list):
        raise TypeError("projectability contract rules must be a list")

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        projectability = rule.get("projectability")
        if projectability in {"INDETERMINATE", "MUST_NOT_INFER"}:
            continue
        if not isinstance(projectability, str):
            continue
        canonical_fact = rule.get("canonical_fact")
        if not isinstance(canonical_fact, str):
            continue
        mapped = _CANONICAL_FIELD_MAP.get(canonical_fact)
        if mapped is None:
            continue
        fact_type, fields = mapped
        fields_by_type.setdefault(fact_type, set()).update(fields)
        field_classes = projectability_by_type.setdefault(fact_type, {})
        for field in fields:
            prior = field_classes.get(field)
            if prior is not None and prior != projectability:
                raise ValueError(
                    "conflicting projectability classes for "
                    f"{fact_type}.{field}: {prior} vs {projectability}"
                )
            field_classes[field] = projectability
        rule_id = rule.get("rule_id")
        if isinstance(rule_id, str):
            rules_by_type.setdefault(fact_type, []).append(rule_id)

    by_fact_type = {
        fact_type: FactComparisonPolicy(
            fact_type=fact_type,
            fields=frozenset(fields),
            rule_ids=tuple(sorted(rules_by_type.get(fact_type, []))),
            field_projectability=dict(projectability_by_type.get(fact_type, {})),
        )
        for fact_type, fields in fields_by_type.items()
    }

    return VerificationPolicy(
        contract_id=str(header.get("id", "unknown")),
        contract_version=str(header.get("version", "unknown")),
        by_fact_type=by_fact_type,
    )
