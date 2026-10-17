"""Mechanical Path B rule-evidence hygiene; never a qualified G1 validator.

The register is not an Edition 5 ruleset, a normative completeness census,
or a means of manufacturing human review. This code deliberately cannot
authorize a G1 pass or confirmatory model inference, even with syntactically
complete records. Authenticity and independence require separate custody.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

from .lri_source_identity import pinned_publication_hashes

_REQUIRED_COMPONENTS = frozenset(
    {"LRI_Common_Component_V3", "LRI_NG_Component_R1", "LAB_FRU_Component"}
)
_PLACEHOLDERS = frozenset({"TBD", "TODO", "UNKNOWN", "PENDING", "PLACEHOLDER"})


@dataclass(frozen=True)
class RuleEvidenceReport:
    rule_count: int
    mechanical_record_checks_complete: bool
    blockers: tuple[str, ...]
    status: str = "PREFREEZE_MECHANICAL_EVIDENCE_ONLY"
    G1_qualified: bool = False
    confirmatory_permission: bool = False


def _valid_reference(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().upper() not in _PLACEHOLDERS
    )


def _valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
        and set(value) != {"0"}
    )


def _load_schema() -> dict[str, Any]:
    resource = files("fhirbridge").joinpath("path_b_rule_evidence.schema.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def assess_path_b_rule_evidence(
    document: dict[str, Any],
    *,
    coverage: dict[str, Any],
    protocol_gates: dict[str, Any],
) -> RuleEvidenceReport:
    """Assess mechanical completeness while guarding the *blocked* research boundary.

    Only use this function on synthetic public templates or protected records
    under proper access controls. Pseudonyms and hashes are not signatures.
    A passed check is not an approval or a G1 validation instrument.
    """
    if not isinstance(document, dict):
        raise ValueError("rule evidence register must be an object")
    errors = list(Draft202012Validator(_load_schema()).iter_errors(document))
    if errors:
        first = sorted(errors, key=lambda e: str(e.json_path))[0]
        raise ValueError(f"invalid Path B evidence format at {first.json_path}: {first.message}")

    boundary = protocol_gates.get("protocol_freeze", {})
    decision = boundary.get("development_path_decision", {})
    scope = coverage.get("path_b_bounded_coverage", {})
    claim = scope.get("claims", {})
    if not (
        boundary.get("status") == "blocked"
        and decision.get("selected") == "bounded_independent_reconstruction"
        and decision.get("confirmatory_permission") is False
        and decision.get("gated_qualification_alternative_implemented") is False
        and scope.get("status") == "incomplete_no_independent_extraction"
        and scope.get("path") == "bounded_independent_reconstruction"
        and claim.get("confirmatory_G1_validity_authorized") is False
        and claim.get("original_IGAMT_profile_conformant") is False
    ):
        raise ValueError("Path B prefreeze boundary changed: refuse development report")

    pinned = pinned_publication_hashes()
    actual_source = document["normative_sources"]
    referenced_source = scope.get("normative_source", {})
    if (
        actual_source["guide_sha256"] != pinned["implementation_guide"]
        or actual_source["errata_sha256"] != pinned["errata_letter"]
        or referenced_source.get("guide_pdf_sha256") != pinned["implementation_guide"]
        or referenced_source.get("errata_letter_sha256") != pinned["errata_letter"]
        or set(actual_source["components"]) != _REQUIRED_COMPONENTS
        or set(scope.get("target", {}).get("components", [])) != _REQUIRED_COMPONENTS
    ):
        raise ValueError("Path B pinned source or component identity mismatch")

    blockers: list[str] = []
    observed_ids: set[str] = set()
    for rule in document["rules"]:
        name = rule["rule_id"]
        if name in observed_ids:
            blockers.append(f"{name}: duplicate rule ID")
        observed_ids.add(name)

        usage = rule["usage"]
        applies = rule["applicability"]
        disposition = rule["disposition"]
        anchor = rule["source_anchor"]
        if usage == "UNKNOWN" or applies in ("UNKNOWN", "UNASSESSED"):
            blockers.append(f"{name}: usage/applicability is unresolved")
        if (usage == "C" or applies == "CONDITIONAL") and not _valid_reference(
            rule["condition"]
        ):
            blockers.append(f"{name}: conditional predicate not established")
        if disposition != "ADJUDICATED":
            blockers.append(f"{name}: not independently adjudicated")
        if disposition == "EXCLUDED_WITH_REASON":
            if not _valid_reference(rule.get("exclusion_reason")):
                blockers.append(f"{name}: exclusion lacks rationale")
            blockers.append(f"{name}: excluded rule needs separately authorized scope review")
        if not anchor["guide_pages"]:
            blockers.append(f"{name}: no guide page citations")
        if anchor["errata_review"] in ("UNASSESSED", "DISPUTED"):
            blockers.append(f"{name}: errata applicability unresolved")
        if anchor["errata_review"] == "APPLICABLE_ERRATA" and not anchor["errata_references"]:
            blockers.append(f"{name}: applicable errata lacks a source reference")

        if disposition != "ADJUDICATED":
            continue

        a, b, adj = rule["reader_a"], rule["reader_b"], rule["adjudicator"]
        if a is None or b is None or adj is None:
            blockers.append(f"{name}: missing original independent readers/adjudicator")
        elif (
            len({a["extractor_pseudonym"], b["extractor_pseudonym"], adj["pseudonym"]})
            != 3
            or not all(
                _valid_digest(rec["response_lock_sha256"])
                for rec in (a, b)
            )
            or a["response_lock_sha256"] == b["response_lock_sha256"]
            or not _valid_reference(adj["private_evidence_ref"])
            or not _valid_reference(adj["double_omission_audit_ref"])
        ):
            blockers.append(f"{name}: original review chain missing or not role-separated")

        positive = rule["positive_control"]
        negative = rule["negative_control"]
        if positive is None or negative is None:
            blockers.append(f"{name}: positive/negative controls not supplied")
        else:
            for label, control in (("positive", positive), ("negative", negative)):
                if (
                    control["result"] != "PASS_EXPECTED_LOCUS"
                    or control["expected_locus"] != rule["locus"]
                    or control["observed_locus"] != rule["locus"]
                    or not _valid_digest(control["evidence_sha256"])
                ):
                    blockers.append(f"{name}: {label} control not evidenced at expected locus")
            if positive["control_id"] == negative["control_id"]:
                blockers.append(f"{name}: positive and negative controls are not distinct")

    inventory = scope.get("required_and_conditional_inventory", {})
    reviews = scope.get("reviews", {})
    testing = scope.get("test_qualification", {})
    denominator = inventory.get("independent_denominator")
    if not isinstance(denominator, int) or isinstance(denominator, bool) or denominator < 1:
        blockers.append("independent bounded R/C completeness denominator is absent")
    elif inventory.get("independently_adjudicated_R_and_C_rows") != denominator:
        blockers.append("not all independently counted R/C rules were adjudicated")
    elif len(document["rules"]) != denominator:
        blockers.append("register size does not match independent bounded denominator")

    for key in (
        "blind_human_extraction_received",
        "distinct_human_adjudicator_assigned",
        "all_disagreements_adjudicated",
        "standards_completeness_certified",
    ):
        if reviews.get(key) is not True:
            blockers.append(f"external reviews not complete: {key}")

    for key in (
        "rule_provenance_and_hashes_pinned",
        "positive_controls_passed",
        "expected_locus_negative_controls_passed",
        "all_11_scenario_families_feasible",
        "independent_validator_review_complete",
    ):
        if testing.get(key) is not True:
            blockers.append(f"independent G1 qualification incomplete: {key}")

    return RuleEvidenceReport(
        rule_count=len(document["rules"]),
        mechanical_record_checks_complete=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
