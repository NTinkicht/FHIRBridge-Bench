"""Independent LRI required-element extraction readiness and comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_COMPARE_FIELDS = (
    "element_kind",
    "usage",
    "cardinality",
    "datatype",
    "max_length",
    "condition",
    "value_set_or_binding_ref",
    "source_grounding_classification",
)


@dataclass(frozen=True)
class ExtractionReadiness:
    ready: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ExtractionComparison:
    source_sha256: str
    extractor_ids: tuple[str, str]
    union_locus_count: int
    exact_agreement_count: int
    exact_agreement_rate: float
    missing_from_a: tuple[str, ...]
    missing_from_b: tuple[str, ...]
    field_disagreements: tuple[dict[str, Any], ...]


def _entries_by_locus(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("entries must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("each extraction entry must be an object")
        locus = item.get("locus")
        if not isinstance(locus, str) or not locus.strip():
            raise ValueError("each extraction entry needs a non-empty locus")
        if locus in result:
            raise ValueError(f"duplicate extracted locus: {locus}")
        result[locus] = item
    return result


def assess_required_element_extraction(
    document: dict[str, Any],
) -> ExtractionReadiness:
    blockers: list[str] = []

    if document.get("extraction_complete") is not True:
        blockers.append("extraction is not marked complete")

    independence = document.get("independence")
    if not isinstance(independence, dict):
        blockers.append("independence declaration is missing")
    else:
        for field in (
            "other_extractor_output_seen_before_completion",
            "project_required_element_inventory_seen_before_completion",
            "renderer_output_used_as_requirement_evidence",
        ):
            if independence.get(field) is not False:
                blockers.append(f"independence condition failed: {field}")

    source = document.get("source")
    if not isinstance(source, dict):
        blockers.append("source metadata is missing")
    else:
        digest = source.get("artifact_sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or set(digest.lower()) <= {"0"}
        ):
            blockers.append("source artifact SHA-256 is missing or placeholder")

    try:
        entries = _entries_by_locus(document)
    except ValueError as exc:
        blockers.append(str(exc))
        entries = {}

    for locus, item in entries.items():
        if item.get("usage") == "UNKNOWN":
            blockers.append(f"{locus}: usage remains UNKNOWN")
        if item.get("source_grounding_classification") == "UNRESOLVED":
            blockers.append(f"{locus}: grounding classification remains UNRESOLVED")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            blockers.append(f"{locus}: evidence is missing")
        elif any(
            isinstance(value, str) and "TO_BE_" in value.upper()
            for value in evidence
        ):
            blockers.append(f"{locus}: evidence still contains a placeholder")

    return ExtractionReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )


def compare_required_element_extractions(
    extraction_a: dict[str, Any],
    extraction_b: dict[str, Any],
) -> ExtractionComparison:
    ready_a = assess_required_element_extraction(extraction_a)
    ready_b = assess_required_element_extraction(extraction_b)
    if not ready_a.ready:
        raise ValueError(
            "extraction A is not ready: " + "; ".join(ready_a.blockers)
        )
    if not ready_b.ready:
        raise ValueError(
            "extraction B is not ready: " + "; ".join(ready_b.blockers)
        )

    source_a = extraction_a["source"]
    source_b = extraction_b["source"]
    if source_a["artifact_sha256"].lower() != source_b["artifact_sha256"].lower():
        raise ValueError("independent extractions do not use the same source artifact")
    if source_a["profile_name"] != source_b["profile_name"]:
        raise ValueError("independent extractions do not use the same profile")

    extractor_a = extraction_a["extractor"]["extractor_id"]
    extractor_b = extraction_b["extractor"]["extractor_id"]
    if extractor_a == extractor_b:
        raise ValueError("independent extraction pair must use different extractor IDs")

    entries_a = _entries_by_locus(extraction_a)
    entries_b = _entries_by_locus(extraction_b)
    loci_a = set(entries_a)
    loci_b = set(entries_b)
    union = sorted(loci_a | loci_b)

    disagreements: list[dict[str, Any]] = []
    exact = 0
    for locus in sorted(loci_a & loci_b):
        differences = {
            field: {
                "extractor_a": entries_a[locus].get(field),
                "extractor_b": entries_b[locus].get(field),
            }
            for field in _COMPARE_FIELDS
            if entries_a[locus].get(field) != entries_b[locus].get(field)
        }
        if differences:
            disagreements.append({"locus": locus, "differences": differences})
        else:
            exact += 1

    return ExtractionComparison(
        source_sha256=source_a["artifact_sha256"].lower(),
        extractor_ids=(str(extractor_a), str(extractor_b)),
        union_locus_count=len(union),
        exact_agreement_count=exact,
        exact_agreement_rate=exact / len(union),
        missing_from_a=tuple(sorted(loci_b - loci_a)),
        missing_from_b=tuple(sorted(loci_a - loci_b)),
        field_disagreements=tuple(disagreements),
    )


def extraction_comparison_to_dict(
    comparison: ExtractionComparison,
) -> dict[str, Any]:
    return {
        "source_sha256": comparison.source_sha256,
        "extractor_ids": list(comparison.extractor_ids),
        "union_locus_count": comparison.union_locus_count,
        "exact_agreement_count": comparison.exact_agreement_count,
        "exact_agreement_rate": comparison.exact_agreement_rate,
        "missing_from_a": list(comparison.missing_from_a),
        "missing_from_b": list(comparison.missing_from_b),
        "field_disagreements": list(comparison.field_disagreements),
        "adjudication_performed": False,
    }
