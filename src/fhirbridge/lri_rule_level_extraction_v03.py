"""Rule-level, *unadjudicated* Path B extraction v0.3 and private locked triage.

This is a parallel, explicitly versioned intake. The old v0.2 extraction
schema, original response bytes, locks and locus-only comparison remain
unchanged. Reader-assigned rule IDs are NOT shared between readers and never
prove scientific equivalence or source completeness.
"""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from fhirbridge.lri_extraction_lock import (
    _UniqueKeysExtractionLoader,
    _same_lock_value,
)
from fhirbridge.lri_source_identity import pinned_publication_hashes

_VERSION = "0.3.0"
_LOCK_VERSION = "0.3.0"
_RULE_FIELDS = (
    "locus",
    "rule_kind",
    "element_kind",
    "usage",
    "cardinality",
    "datatype",
    "max_length",
    "condition",
    "value_set_or_binding_ref",
    "source_grounding_classification",
    "related_loci",
)


@dataclass(frozen=True)
class RuleLevelTriage:
    original_response_sha256: tuple[str, str]
    reader_ids: tuple[str, str]
    candidate_counts: tuple[int, int]
    mechanically_identical_content_pairs: tuple[dict[str, Any], ...]
    reader_a_only_candidates: tuple[dict[str, Any], ...]
    reader_b_only_candidates: tuple[dict[str, Any], ...]
    citation_or_rationale_differences: tuple[dict[str, Any], ...]
    per_locus_candidate_counts: tuple[dict[str, Any], ...]
    unreviewed_or_unresolved_rule_count: int

    @property
    def status(self) -> str:
        return "PRIVATE_RULE_LEVEL_CANDIDATE_TRIAGE_NO_ADJUDICATION"

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
    def G1_qualified(self) -> bool:
        return False

    @property
    def confirmatory_permission(self) -> bool:
        return False


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(
        files("fhirbridge")
        .joinpath("lri_rule_level_extraction_v03.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _canonical_rule(rule: dict[str, Any]) -> str:
    """Content key: candidate IDs and reviewer prose must not drive matching."""
    normalized = {
        field: sorted(rule.get(field) or [])
        if field == "related_loci" else rule.get(field)
        for field in _RULE_FIELDS
    }
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _reject_nonnormative_placeholders(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    upper = value.upper()
    return any(marker in upper for marker in ("TO_BE_", "TBD", "PLACEHOLDER"))


def assess_rule_level_v03(document: dict[str, Any]) -> tuple[str, ...]:
    """Check v0.3 input shape and candidate integrity, not normative correctness.

    An apparently complete record may still omit every requirement in an
    official source. No software status is an independent coverage certificate.
    """
    if type(document) is not dict:
        return ("v0.3 extraction must be a mapping",)
    blockers = []
    for problem in _validator().iter_errors(document):
        at = "/" + "/".join(str(p) for p in problem.absolute_path)
        blockers.append(f"v0.3 schema error {at} ({problem.validator})")
    if document.get("schema_version") != _VERSION:
        blockers.append("v0.3 schema_version mismatch")
    if _reject_nonnormative_placeholders(document.get("extraction_id")):
        blockers.append("extraction ID missing or placeholder")
    ext = document.get("extractor")
    if type(ext) is not dict or _reject_nonnormative_placeholders(ext.get("extractor_id")):
        blockers.append("extractor identity missing or placeholder")
    source = document.get("source")
    pins = pinned_publication_hashes()
    if type(source) is not dict or any(
        source.get(k) != pins[p]
        for k, p in (
            ("artifact_sha256", "implementation_guide"),
            ("errata_artifact_sha256", "errata_letter"),
        )
    ):
        blockers.append("v0.3 source hashes do not match pinned Edition 5 and errata")
    if type(source) is not dict or source.get("artifact_type") != "edition5_publication_pdf":
        blockers.append("v0.3 source must identify approved Edition 5 publication")
    independence = document.get("independence")
    if type(independence) is not dict or any(
        independence.get(flag) is not False
        for flag in (
            "other_extractor_output_seen_before_completion",
            "project_required_element_inventory_seen_before_completion",
            "renderer_output_used_as_requirement_evidence",
        )
    ):
        blockers.append("v0.3 isolation conditions missing or failed")
    entries = document.get("entries")
    if type(entries) is not list or not entries:
        blockers.append("v0.3 entries must be nonempty")
        return tuple(sorted(set(blockers)))
    ids: set[str] = set()
    signatures: set[str] = set()
    for index, rule in enumerate(entries):
        if type(rule) is not dict:
            blockers.append(f"candidate entry {index} not a mapping")
            continue
        rid = rule.get("candidate_rule_id")
        if type(rid) is not str or _reject_nonnormative_placeholders(rid):
            blockers.append(f"candidate entry {index} missing unique rule ID")
        elif rid in ids:
            blockers.append(f"duplicate candidate rule ID: {rid}")
        else:
            ids.add(rid)
        if _reject_nonnormative_placeholders(rule.get("locus")):
            blockers.append(f"candidate entry {index} physical locus missing")
        if rule.get("usage") == "C" and _reject_nonnormative_placeholders(
            rule.get("condition")
        ):
            blockers.append(f"candidate entry {index} conditional predicate missing")
        if rule.get("usage") == "UNKNOWN" or rule.get(
            "source_grounding_classification"
        ) == "UNRESOLVED":
            blockers.append(f"candidate entry {index} is unresolved")
        if _reject_nonnormative_placeholders(rule.get("cardinality")):
            blockers.append(f"candidate entry {index} cardinality missing")
        if not rule.get("evidence") or any(
            _reject_nonnormative_placeholders(value)
            for value in rule.get("evidence", [])
        ):
            blockers.append(f"candidate entry {index} source citation missing")
        if rule.get("rule_kind") == "CROSS_FIELD" and not rule.get("related_loci"):
            blockers.append(f"candidate entry {index} cross-field related loci missing")
        # Skip invalid input signatures; jsonschema findings already block.
        try:
            signature = _canonical_rule(rule)
        except (TypeError, ValueError):
            blockers.append(f"candidate entry {index} cannot be normalized")
            continue
        if signature in signatures:
            blockers.append(
                f"duplicate substantive candidate at same locus: {rule.get('locus')}"
            )
        signatures.add(signature)
    if document.get("extraction_complete") is not True:
        blockers.append("candidate v0.3 extraction not self-declared complete")
    return tuple(sorted(set(blockers)))


def parse_v03_original(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw:
        raise ValueError("missing original v0.3 response bytes")
    try:
        doc = yaml.load(raw.decode("utf-8", errors="strict"), Loader=_UniqueKeysExtractionLoader)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("v0.3 original is not unambiguous UTF-8 YAML") from exc
    if type(doc) is not dict or doc.get("schema_version") != _VERSION:
        raise ValueError("original is not explicit v0.3 extraction")
    return doc


def create_v03_response_lock(raw: bytes) -> dict[str, Any]:
    doc = parse_v03_original(raw)
    problems = assess_rule_level_v03(doc)
    if any(
        "schema error" in p
        or "source hashes" in p
        or "source must" in p
        or "isolation conditions" in p
        or "identity missing" in p
        or "ID missing" in p
        or "duplicate candidate" in p
        for p in problems
    ):
        raise ValueError("v0.3 response cannot be locked: " + "; ".join(problems))
    return {
        "lock_schema_version": _LOCK_VERSION,
        "status": "RULE_LEVEL_V03_ORIGINAL_HASHED_NOT_HUMAN_ATTESTED",
        "response_sha256": sha256(raw).hexdigest(),
        "extraction_id": doc["extraction_id"],
        "extractor_id": doc["extractor"]["extractor_id"],
        "source_sha256": pinned_publication_hashes()["implementation_guide"],
        "errata_sha256": pinned_publication_hashes()["errata_letter"],
        "candidate_rule_count": len(doc["entries"]),
        "metadata_ready": len(problems) == 0,
        "readiness_blockers": list(problems),
        "independently_verified_completeness": False,
        "qualified_G1": False,
        "adjudication_performed": False,
        "confirmatory_permission": False,
    }


def verify_v03_response_lock(raw: bytes, lock: dict[str, Any]) -> dict[str, Any]:
    if type(lock) is not dict or lock.get("lock_schema_version") != _LOCK_VERSION:
        raise ValueError("invalid v0.3 lock version")
    fresh = create_v03_response_lock(raw)
    if not _same_lock_value(fresh, lock):
        raise ValueError("v0.3 original bytes or lock metadata changed")
    return parse_v03_original(raw)


def _summarize(rule: dict[str, Any]) -> dict[str, Any]:
    """Candidate output is for private human adjudication, never public CI."""
    return deepcopy(rule)


def triage_locked_v03_extractions(
    raw_a: bytes,
    lock_a: dict[str, Any],
    raw_b: bytes,
    lock_b: dict[str, Any],
) -> RuleLevelTriage:
    """Strict content matching *only*: no inferred alignment by reader rule IDs.

    Divergent claimed predicates at the same physical locus remain separate
    unmatched candidates. Equal content is merely a candidate for review;
    source citations/interpretations are still independently audited.
    """
    a = verify_v03_response_lock(raw_a, lock_a)
    b = verify_v03_response_lock(raw_b, lock_b)
    if lock_a["extractor_id"] == lock_b["extractor_id"]:
        raise ValueError("v0.3 readers must have separate IDs")

    def index(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for item in doc["entries"]:
            signature = _canonical_rule(item)
            if signature in out:
                raise ValueError("duplicate candidate content")
            out[signature] = item
        return out

    left, right = index(a), index(b)
    observed_a = Counter(rule["locus"] for rule in a["entries"])
    observed_b = Counter(rule["locus"] for rule in b["entries"])
    shared = sorted(set(left) & set(right))
    unmatched_a = sorted(set(left) - set(right))
    unmatched_b = sorted(set(right) - set(left))
    provenance = []
    for signature in shared:
        first, second = left[signature], right[signature]
        if (
            first.get("evidence") != second.get("evidence")
            or first.get("classification_rationale") != second.get("classification_rationale")
        ):
            provenance.append({
                "locus": first["locus"],
                "reader_a_rule_id": first["candidate_rule_id"],
                "reader_b_rule_id": second["candidate_rule_id"],
                "source_or_rationale_differs": True,
                "human_source_audit_required": True,
            })
    return RuleLevelTriage(
        original_response_sha256=(lock_a["response_sha256"], lock_b["response_sha256"]),
        reader_ids=(lock_a["extractor_id"], lock_b["extractor_id"]),
        candidate_counts=(len(left), len(right)),
        mechanically_identical_content_pairs=tuple({
            "locus": left[key]["locus"],
            "reader_a_rule_id": left[key]["candidate_rule_id"],
            "reader_b_rule_id": right[key]["candidate_rule_id"],
            "human_source_audit_required": True,
        } for key in shared),
        reader_a_only_candidates=tuple({
            "entry": _summarize(left[key]),
            "same_locus_exists_in_other_reader": observed_b[left[key]["locus"]] > 0,
            "human_rule_reconciliation_required": True,
        } for key in unmatched_a),
        reader_b_only_candidates=tuple({
            "entry": _summarize(right[key]),
            "same_locus_exists_in_other_reader": observed_a[right[key]["locus"]] > 0,
            "human_rule_reconciliation_required": True,
        } for key in unmatched_b),
        citation_or_rationale_differences=tuple(provenance),
        per_locus_candidate_counts=tuple({
            "locus": locus,
            "reader_a_count": observed_a[locus],
            "reader_b_count": observed_b[locus],
            "identical_content_pairs": sum(
                left[key]["locus"] == locus for key in shared
            ),
            "human_completeness_audit_required": True,
        } for locus in sorted(set(observed_a) | set(observed_b))),
        unreviewed_or_unresolved_rule_count=sum(
            rule["usage"] == "UNKNOWN" or rule["source_grounding_classification"] == "UNRESOLVED"
            for rule in list(a["entries"]) + list(b["entries"])
        ),
    )
