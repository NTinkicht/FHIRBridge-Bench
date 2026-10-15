"""Private pre-adjudication handoff for independently locked Path B extractions.

No determination of standards conformance, reviewer independence, coverage
completeness or scientific readiness is made by this module.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fhirbridge.lri_extraction_lock import (
    compare_locked_extractions,
    verify_response_lock,
)

# A full agreement census is the conservative default. A later, separately
# preregistered and approved sampling protocol could replace this approach,
# but this tool does not infer or select a post-hoc sample.
_HANDOFF_VERSION = "0.1.0"
_AUDIT_MODE = "ALL_OBSERVED_AGREEMENTS"
_COMPARE_ATTRIBUTES = (
    "element_kind",
    "usage",
    "cardinality",
    "datatype",
    "max_length",
    "condition",
    "value_set_or_binding_ref",
    "source_grounding_classification",
)
_COVERAGE_TARGETS = (
    "MSH",
    "PID",
    "ORC",
    "OBR",
    "OBX",
    "SPM",
    "NTE_IF_PRESENT",
    "CROSS_SEGMENT_PREDICATES",
    "VOCABULARY_AND_DATATYPE_BINDINGS",
    "COMMON_NG_FRU_COMPONENT_INTERACTIONS",
    "DECEMBER_2024_ERRATA_EFFECTS",
    "ADDITIONAL_APPLICABLE_LOCI_NOT_IN_EITHER_EXTRACTION",
)


def _indexed(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("extraction has no entries")
    output: dict[str, dict[str, Any]] = {}
    for entry in entries:
        locus = entry["locus"]
        if locus in output:
            raise ValueError("duplicate extraction locus")
        output[locus] = entry
    return output


def build_adjudication_handoff(
    raw_a: bytes,
    lock_a: dict[str, Any],
    raw_b: bytes,
    lock_b: dict[str, Any],
) -> dict[str, Any]:
    """List all observed rules for human review after original records are locked.

    Distinguish the **observed union** from the unknown standards denominator:
    independently omitted requirements cannot be discovered by agreement.
    """

    comparison = compare_locked_extractions(raw_a, lock_a, raw_b, lock_b)
    if comparison["status"] != "LOCKED_UNADJUDICATED_COMPARISON_ONLY":
        raise ValueError(
            "both locked extractions must be metadata-ready before handoff; "
            "preserve incomplete original responses without forcing qualification"
        )
    first = verify_response_lock(raw_a, lock_a)
    second = verify_response_lock(raw_b, lock_b)
    left = _indexed(first)
    right = _indexed(second)

    rows: list[dict[str, Any]] = []
    counts = {"one_reader_only": 0, "field_disagreements": 0, "observed_agreements": 0}
    for locus in sorted(set(left) | set(right)):
        a, b = left.get(locus), right.get(locus)
        if a is None or b is None:
            category = "ONE_READER_ONLY"
            counts["one_reader_only"] += 1
        elif any(a.get(k) != b.get(k) for k in _COMPARE_ATTRIBUTES):
            category = "FIELD_DISAGREEMENT"
            counts["field_disagreements"] += 1
        else:
            category = "OBSERVED_AGREEMENT_NEEDS_EVIDENCE_AUDIT"
            counts["observed_agreements"] += 1
        provenance_disagreement = (
            a is not None
            and b is not None
            and (
                a.get("evidence") != b.get("evidence")
                or a.get("classification_rationale") != b.get("classification_rationale")
            )
        )
        rows.append(
            {
                "locus": locus,
                "review_category": category,
                "reader_a_entry": deepcopy(a),
                "reader_b_entry": deepcopy(b),
                "citation_or_rationale_differs": provenance_disagreement,
                "source_level_independent_adjudication_required": True,
                "human_disposition": None,
                "human_source_evidence": [],
            }
        )

    # A 100% agreement rate in the observed union is NOT a measure of whether
    # both readers omitted the same mandatory or conditional rule.
    scope_audit = [
        {
            "coverage_area": name,
            "status": "NOT_REVIEWED",
            "newly_discovered_omissions": None,
            "independent_source_evidence": [],
            "reviewer_attestation": None,
        }
        for name in _COVERAGE_TARGETS
    ]
    observed = comparison["comparison"]
    if len(rows) != observed["union_locus_count"]:
        raise ValueError("handoff does not match the locked comparison union")
    if counts["observed_agreements"] != observed["exact_agreement_count"]:
        raise ValueError("handoff does not match observed field agreements")
    if counts["one_reader_only"] != (
        len(observed["missing_from_a"]) + len(observed["missing_from_b"])
    ):
        raise ValueError("handoff does not match missing-locus accounting")
    if counts["field_disagreements"] != len(observed["field_disagreements"]):
        raise ValueError("handoff does not match field disagreement accounting")

    return {
        "schema_version": _HANDOFF_VERSION,
        "status": "PRIVATE_PRE_ADJUDICATION_REVIEW_REQUIRED",
        "source_sha256": observed["source_sha256"],
        "errata_sha256": observed["errata_sha256"],
        "original_response_sha256": comparison["raw_response_hashes"],
        "extractor_ids": [lock_a["extractor_id"], lock_b["extractor_id"]],
        "agreement_audit_plan": {
            "mode": _AUDIT_MODE,
            "selected_all_observed_agreement_loci": True,
            "requires_separate_human_evidence_review": True,
            "posthoc_agreement_sample_selected": False,
            "method_approval_asserted": False,
        },
        "observed_union_counts": {
            "total": len(rows),
            **counts,
        },
        "observed_field_agreement_rate": observed["exact_agreement_rate"],
        "adjudication_rows": rows,
        "independent_scope_completeness_audit": scope_audit,
        "independently_established_requirements_denominator": None,
        "omissions_in_both_extractions_checked": False,
        "all_disagreements_adjudicated": False,
        "all_agreements_source_audited": False,
        "human_adjudication_performed": False,
        "reviewer_independence_verified_by_software": False,
        "standards_completeness_certified": False,
        "G1_qualified": False,
        "confirmatory_permission": False,
    }
