"""Rule-level third-source omissions triage over private v0.3 original locks.

A separate census can flag a *proposed* requirement missing from both
first-round readers, even when the field itself is present. This tool NEVER
certifies the independent denominator, scientific source completeness, reviewer
independence or G1. No protected standards excerpts belong in public CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from jsonschema import Draft202012Validator

from fhirbridge.lri_lock_json import load_coordinator_lock_json
from fhirbridge.lri_rule_level_extraction_v03 import (
    _canonical_rule,
    _reject_nonnormative_placeholders,
    _validator,
    verify_v03_response_lock,
)
from fhirbridge.path_b_source_census import (
    _check_census,
    _pages,
)

_CENSUS_VERSION = "0.3.0"
_CENSUS_STATUS = "UNADJUDICATED_V03_RULE_LEVEL_CENSUS_DRAFT"
_TOP_LEVEL = {
    "schema_version",
    "status",
    "census_reviewer_id",
    "source_sha256",
    "errata_sha256",
    "scope_areas",
    "candidate_requirements",
}
_RECORD_FIELDS = {"coverage_area", "source_pages", "rule"}


@dataclass(frozen=True)
class RuleLevelSourceCensusTriage:
    first_reader_sha256: str
    second_reader_sha256: str
    third_source_census_sha256: str
    candidate_rule_count: int
    distinct_candidate_locus_count: int
    rules_not_found_in_either_reader: tuple[str, ...]
    same_locus_but_no_matching_rule: tuple[str, ...]
    matching_candidate_rules_requiring_human_review: tuple[str, ...]
    unreviewed_scope_areas: tuple[str, ...]
    census_reviewer_id: str

    @property
    def status(self) -> str:
        return "PRIVATE_V03_RULE_LEVEL_CENSUS_TRIAGE_ONLY"

    @property
    def independently_established_requirements_denominator(self) -> None:
        return None

    @property
    def human_adjudication_performed(self) -> bool:
        return False

    @property
    def scientific_completeness_certified(self) -> bool:
        return False

    @property
    def reviewer_independence_verified_by_software(self) -> bool:
        return False

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def confirmatory_permission(self) -> bool:
        return False


def _validate_census(census: Any, *, extractor_ids: list[str]) -> dict[str, str]:
    if type(census) is not dict or set(census) != _TOP_LEVEL:
        raise ValueError("v0.3 census fields incomplete or unsupported")
    if (
        census["schema_version"] != _CENSUS_VERSION
        or census["status"] != _CENSUS_STATUS
    ):
        raise ValueError("v0.3 source census version or draft status invalid")
    # Reuse the proven bounded area/pinned-publication identity checker with
    # a *temporary* metadata-only v0.2-shaped object. Never pass v0.3 rule
    # candidates into the v0.2 locus-level matching code.
    scope_only = {
        **census,
        "schema_version": "0.1.0",
        "status": "UNADJUDICATED_SOURCE_CENSUS_DRAFT",
        "candidate_requirements": [],
    }
    return _check_census(scope_only, extractors=extractor_ids)


def audit_v03_independent_source_census(
    *,
    raw_a: bytes,
    lock_a: dict[str, Any],
    raw_b: bytes,
    lock_b: dict[str, Any],
    source_census_json_bytes: bytes,
) -> RuleLevelSourceCensusTriage:
    """Compare independent candidate rule *contents*, never reader IDs alone."""
    first = verify_v03_response_lock(raw_a, lock_a)
    second = verify_v03_response_lock(raw_b, lock_b)
    if lock_a["extractor_id"] == lock_b["extractor_id"]:
        raise ValueError("independent original readers must have distinct IDs")
    census = load_coordinator_lock_json(source_census_json_bytes)
    by_area = _validate_census(
        census, extractor_ids=[lock_a["extractor_id"], lock_b["extractor_id"]]
    )
    reviewed_pages = {
        row["coverage_area"]: frozenset(row["source_pages"])
        for row in census["scope_areas"]
        if row["status"] == "SOURCE_PAGES_CHECKED"
    }
    candidates = census["candidate_requirements"]
    if type(candidates) is not list:
        raise ValueError("v0.3 source census candidates must be an array")
    # Schema validation operates on *candidate entries* only, not the old
    # physical-locus-unique v0.2 full extraction object.
    rule_validator = Draft202012Validator(_validator().schema["$defs"]["entry"])
    first_signatures = {_canonical_rule(e) for e in first["entries"]}
    second_signatures = {_canonical_rule(e) for e in second["entries"]}
    observed_loci = {e["locus"] for e in first["entries"] + second["entries"]}
    seen_ids: set[str] = set()
    seen_rule_content: set[str] = set()
    candidate_loci: set[str] = set()
    missing: list[str] = []
    same_locus: list[str] = []
    matched: list[str] = []
    for index, candidate in enumerate(candidates):
        if type(candidate) is not dict or set(candidate) != _RECORD_FIELDS:
            raise ValueError("invalid v0.3 third-source census record fields")
        area = candidate["coverage_area"]
        pages = candidate["source_pages"]
        rule = candidate["rule"]
        if (
            type(area) is not str
            or by_area.get(area) != "SOURCE_PAGES_CHECKED"
            or not _pages(pages)
            or not set(pages).issubset(reviewed_pages.get(area, ()))
        ):
            raise ValueError("census rule not grounded in a checked source area/pages")
        if type(rule) is not dict or any(rule_validator.iter_errors(rule)):
            raise ValueError(f"v0.3 census rule {index} fails candidate schema")
        rule_id = rule["candidate_rule_id"]
        if (
            _reject_nonnormative_placeholders(rule_id)
            or rule_id in seen_ids
            or _reject_nonnormative_placeholders(rule["locus"])
            or rule["usage"] not in ("R", "C")
            or rule["source_grounding_classification"] != "SOURCE_FACT"
            or _reject_nonnormative_placeholders(rule.get("cardinality"))
            or any(
                _reject_nonnormative_placeholders(item)
                for item in rule.get("evidence", [])
            )
            or (
                (rule["usage"] == "C" or rule["rule_kind"] == "CONDITIONAL_PREDICATE")
                and _reject_nonnormative_placeholders(rule.get("condition"))
            )
            or (
                rule["rule_kind"] == "DATATYPE"
                and _reject_nonnormative_placeholders(rule.get("datatype"))
            )
            or (
                rule["rule_kind"] == "VALUE_SET_BINDING"
                and _reject_nonnormative_placeholders(
                    rule.get("value_set_or_binding_ref")
                )
            )
            or (
                rule["rule_kind"] == "CROSS_FIELD"
                and not rule.get("related_loci")
            )
        ):
            raise ValueError("v0.3 third-source census has invalid rule identity/constraint")
        seen_ids.add(rule_id)
        signature = _canonical_rule(rule)
        if signature in seen_rule_content:
            raise ValueError("duplicate substantive third-source census rule")
        seen_rule_content.add(signature)
        locus = rule["locus"]
        candidate_loci.add(locus)
        if signature in first_signatures or signature in second_signatures:
            # A matching proposed rule is still independently source-audited.
            matched.append(rule_id)
        else:
            missing.append(rule_id)
            if locus in observed_loci:
                same_locus.append(rule_id)
    return RuleLevelSourceCensusTriage(
        first_reader_sha256=sha256(raw_a).hexdigest(),
        second_reader_sha256=sha256(raw_b).hexdigest(),
        third_source_census_sha256=sha256(source_census_json_bytes).hexdigest(),
        candidate_rule_count=len(candidates),
        distinct_candidate_locus_count=len(candidate_loci),
        rules_not_found_in_either_reader=tuple(sorted(missing)),
        same_locus_but_no_matching_rule=tuple(sorted(same_locus)),
        matching_candidate_rules_requiring_human_review=tuple(sorted(matched)),
        unreviewed_scope_areas=tuple(sorted(
            area for area, status in by_area.items() if status == "UNREVIEWED"
        )),
        census_reviewer_id=census["census_reviewer_id"],
    )
