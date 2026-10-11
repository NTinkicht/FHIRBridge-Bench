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

_REQUIRED_PROJECTABILITY = frozenset({"MUST_PRESERVE", "MAY_TRANSFORM"})


@dataclass(frozen=True)
class FactComparisonPolicy:
    """Fields and projectability classes scored for one canonical fact type."""

    fact_type: str
    fields: frozenset[str]
    rule_ids: tuple[str, ...]
    field_projectability: dict[str, str]
    field_rule_ids: dict[str, tuple[str, ...]]
    field_allowed_operations: dict[str, frozenset[str]]

    def scores(self, field: str) -> bool:
        return field in self.fields

    def projectability(self, field: str) -> str | None:
        return self.field_projectability.get(field)

    def rules_for_field(self, field: str) -> tuple[str, ...]:
        """Return frozen contract rule IDs licensing one canonical field."""

        return self.field_rule_ids.get(field, ())

    def allowed_operations(self, field: str) -> frozenset[str]:
        """Return contract operations licensed for one canonical field."""

        return self.field_allowed_operations.get(field, frozenset())

    def required_fields(self) -> frozenset[str]:
        """Fields whose source assertions must survive in some licensed form."""

        return frozenset(
            field
            for field, projectability in self.field_projectability.items()
            if projectability in _REQUIRED_PROJECTABILITY
        )


@dataclass(frozen=True)
class GroundingGuard:
    """Representation-independent source-grounding invariant."""

    guard_id: str
    source_fact_type: str
    source_field: str
    target_fact_type: str
    target_field: str
    match_type: str
    primary_endpoint_eligible: bool = True
    additional_source_fact_types: tuple[str, ...] = ()
    additional_source_relation_type: str | None = None


@dataclass(frozen=True)
class VerificationPolicy:
    """Contract-derived semantic comparison policy."""

    contract_id: str
    contract_version: str
    by_fact_type: dict[str, FactComparisonPolicy]
    must_not_infer_rule_ids: tuple[str, ...]
    grounding_guards: tuple[GroundingGuard, ...] = ()

    def scores(self, fact_type: str, field: str) -> bool:
        policy = self.by_fact_type.get(fact_type)
        return policy is not None and policy.scores(field)

    def projectability(self, fact_type: str, field: str) -> str | None:
        policy = self.by_fact_type.get(fact_type)
        if policy is None:
            return None
        return policy.projectability(field)

    def rules_for_field(self, fact_type: str, field: str) -> tuple[str, ...]:
        """Return contract rule IDs that place one fact field in scoring scope."""

        policy = self.by_fact_type.get(fact_type)
        if policy is None:
            return ()
        return policy.rules_for_field(field)

    def allowed_operations(self, fact_type: str, field: str) -> frozenset[str]:
        policy = self.by_fact_type.get(fact_type)
        if policy is None:
            return frozenset()
        return policy.allowed_operations(field)

    def allows_operation(self, fact_type: str, field: str, operation: str) -> bool:
        return operation in self.allowed_operations(fact_type, field)

    def required_fields(self, fact_type: str) -> frozenset[str]:
        """Return fields that make absence of this source fact scoreable."""

        policy = self.by_fact_type.get(fact_type)
        if policy is None:
            return frozenset()
        return policy.required_fields()

    def has_required_scope(self, fact_type: str) -> bool:
        return bool(self.required_fields(fact_type))

    @property
    def forbids_ungrounded_inference(self) -> bool:
        """Whether the contract contains an explicit MUST_NOT_INFER rule."""

        return bool(self.must_not_infer_rule_ids)


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
    # Subject attribution remains outside the current v0.2 contract. These
    # mappings are future-facing: they become scoreable only if an externally
    # reviewed contract adds the corresponding canonical rule.
    "report.subject": ("diagnostic_report", ("subject_ref",)),
    "observation.subject": ("observation", ("subject_ref",)),
    "specimen.subject": ("specimen", ("subject_ref",)),
}


def compile_verification_policy(contract: dict[str, Any]) -> VerificationPolicy:
    """Compile supported contract rules into a comparison policy.

    ``INDETERMINATE`` rules are excluded from confirmatory scoring.
    ``MUST_NOT_INFER`` rules are retained separately so unsupported target facts
    can be classified as fabrication only when the contract explicitly forbids
    ungrounded inference. The projectability class and governing rule IDs are
    retained per canonical field so later classification and audit export can
    cite the exact contract basis without consulting renderer logic.
    """

    header = contract.get("contract", {})
    fields_by_type: dict[str, set[str]] = {}
    rules_by_type: dict[str, list[str]] = {}
    projectability_by_type: dict[str, dict[str, str]] = {}
    rules_by_field: dict[str, dict[str, set[str]]] = {}
    operations_by_field: dict[str, dict[str, set[str]]] = {}
    must_not_infer_rule_ids: set[str] = set()

    rules = contract.get("rules", [])
    if not isinstance(rules, list):
        raise TypeError("projectability contract rules must be a list")

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        projectability = rule.get("projectability")
        rule_id = rule.get("rule_id")
        if projectability == "MUST_NOT_INFER":
            if isinstance(rule_id, str):
                must_not_infer_rule_ids.add(rule_id)
            continue
        if projectability == "INDETERMINATE":
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
        operations = rule.get("allowed_operations", [])
        if not isinstance(operations, list) or not all(
            isinstance(operation, str) for operation in operations
        ):
            raise ValueError(
                f"allowed_operations must be a list of strings for rule {rule_id!r}"
            )
        for field in fields:
            prior = field_classes.get(field)
            if prior is not None and prior != projectability:
                raise ValueError(
                    "conflicting projectability classes for "
                    f"{fact_type}.{field}: {prior} vs {projectability}"
                )
            field_classes[field] = projectability
            operations_by_field.setdefault(fact_type, {}).setdefault(field, set()).update(
                operations
            )
            if isinstance(rule_id, str):
                rules_by_field.setdefault(fact_type, {}).setdefault(field, set()).add(
                    rule_id
                )
        if isinstance(rule_id, str):
            rules_by_type.setdefault(fact_type, []).append(rule_id)

    by_fact_type = {
        fact_type: FactComparisonPolicy(
            fact_type=fact_type,
            fields=frozenset(fields),
            rule_ids=tuple(sorted(set(rules_by_type.get(fact_type, [])))),
            field_projectability=dict(projectability_by_type.get(fact_type, {})),
            field_rule_ids={
                field: tuple(sorted(rule_ids))
                for field, rule_ids in rules_by_field.get(fact_type, {}).items()
            },
            field_allowed_operations={
                field: frozenset(operations)
                for field, operations in operations_by_field.get(fact_type, {}).items()
            },
        )
        for fact_type, fields in fields_by_type.items()
    }

    grounding_guards: list[GroundingGuard] = []
    for guard in contract.get("grounding_guards", []):
        if not isinstance(guard, dict):
            raise ValueError("grounding_guards entries must be objects")
        status = guard.get("status", "draft")
        if status == "disabled":
            continue
        fields = {
            key: guard.get(key)
            for key in (
                "guard_id",
                "source_fact_type",
                "source_field",
                "target_fact_type",
                "target_field",
                "match_type",
            )
        }
        if not all(isinstance(value, str) and value for value in fields.values()):
            raise ValueError("grounding guard identity/field values must be strings")
        extras = guard.get("additional_source_fact_types", [])
        if (
            not isinstance(extras, list)
            or not all(isinstance(item, str) and item.strip() for item in extras)
            or len(extras) != len(set(extras))
            or fields["source_fact_type"] in extras
        ):
            raise ValueError(
                "grounding guard additional_source_fact_types must be distinct "
                "nonempty fact types, excluding source_fact_type"
            )
        relation_type = guard.get("additional_source_relation_type")
        if extras and (not isinstance(relation_type, str) or not relation_type):
            raise ValueError(
                "grounding guard with additional_source_fact_types requires "
                "additional_source_relation_type"
            )
        if not extras and relation_type is not None:
            raise ValueError(
                "grounding guard source relation requires additional source fact types"
            )
        if fields["match_type"] != "exact_scalar_membership":
            raise ValueError(
                f"unsupported grounding guard match_type: {fields['match_type']!r}"
            )
        grounding_guards.append(
            GroundingGuard(
                guard_id=fields["guard_id"],
                source_fact_type=fields["source_fact_type"],
                additional_source_fact_types=tuple(extras),
                additional_source_relation_type=relation_type,
                source_field=fields["source_field"],
                target_fact_type=fields["target_fact_type"],
                target_field=fields["target_field"],
                match_type=fields["match_type"],
                primary_endpoint_eligible=bool(
                    guard.get("primary_endpoint_eligible", True)
                ),
            )
        )

    return VerificationPolicy(
        contract_id=str(header.get("id", "unknown")),
        contract_version=str(header.get("version", "unknown")),
        by_fact_type=by_fact_type,
        must_not_infer_rule_ids=tuple(sorted(must_not_infer_rule_ids)),
        grounding_guards=tuple(grounding_guards),
    )
