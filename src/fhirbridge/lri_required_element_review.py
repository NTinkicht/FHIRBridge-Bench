"""Independent LRI required-element extraction readiness and comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fhirbridge.lri_source_identity import pinned_publication_hashes

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
    errata_sha256: str
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


def _unfinished(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    upper = value.upper()
    return any(token in upper for token in ("TO_BE_", "TO-BE-", "TO BE ", "TBD"))


def _sha256_present(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdefABCDEF" for char in value)
        and set(value.lower()) != {"0"}
    )


def assess_required_element_extraction(
    document: dict[str, Any],
) -> ExtractionReadiness:
    """Assess declared extraction quality, not scientific coverage completeness."""

    blockers: list[str] = []

    if document.get("schema_version") != "0.2.0":
        blockers.append("extraction schema_version is not 0.2.0")
    if _unfinished(document.get("extraction_id")):
        blockers.append("extraction_id is missing or placeholder")
    if document.get("extraction_complete") is not True:
        blockers.append("extraction is not marked complete")

    extractor = document.get("extractor")
    if not isinstance(extractor, dict) or _unfinished(extractor.get("extractor_id")):
        blockers.append("extractor_id is missing or placeholder")

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
        pinned = pinned_publication_hashes()
        guide_sha = source.get("artifact_sha256")
        errata_sha = source.get("errata_artifact_sha256")
        if not _sha256_present(guide_sha):
            blockers.append("source artifact SHA-256 is missing or placeholder")
        elif guide_sha.lower() != pinned["implementation_guide"]:
            blockers.append("source artifact SHA-256 differs from pinned Edition 5 guide")
        if not _sha256_present(errata_sha):
            blockers.append("source errata artifact SHA-256 is missing or placeholder")
        elif errata_sha.lower() != pinned["errata_letter"]:
            blockers.append("source errata artifact SHA-256 differs from pinned 2024DEC errata")
        if source.get("artifact_type") != "edition5_publication_pdf":
            blockers.append("source artifact type is not the approved Path B PDF source")
        if source.get("profile_name") != "LRI_NG_FRU_Profile_V3":
            blockers.append("source target profile is not the selected general-lab profile")
        if source.get("edition") != "5" or source.get("errata") != "2024DEC":
            blockers.append("source Edition 5/2024DEC version is not pinned")
        components = source.get("components")
        expected = {
            "LRI_Common_Component_V3",
            "LRI_NG_Component_R1",
            "LAB_FRU_Component",
        }
        if not isinstance(components, list) or len(components) != 3 or set(
            value for value in components if isinstance(value, str)
        ) != expected:
            blockers.append("source Common/NG/FRU component set is not exact")

    try:
        entries = _entries_by_locus(document)
    except ValueError as exc:
        blockers.append(str(exc))
        entries = {}

    for locus, item in entries.items():
        if _unfinished(locus):
            blockers.append(f"{locus}: locus is missing or placeholder")
        if item.get("usage") not in {"R", "RE", "C", "O", "X", "UNKNOWN"}:
            blockers.append(f"{locus}: usage is invalid")
        elif item.get("usage") == "UNKNOWN":
            blockers.append(f"{locus}: usage remains UNKNOWN")
        if item.get("source_grounding_classification") not in {
            "SOURCE_FACT", "PROFILE_CONSTANT", "ENVELOPE", "DERIVED",
            "UNPROJECTABLE", "UNRESOLVED",
        }:
            blockers.append(f"{locus}: grounding classification is invalid")
        elif item.get("source_grounding_classification") == "UNRESOLVED":
            blockers.append(f"{locus}: grounding classification remains UNRESOLVED")
        if _unfinished(item.get("cardinality")):
            blockers.append(f"{locus}: cardinality is missing or placeholder")
        if item.get("usage") == "C" and _unfinished(item.get("condition")):
            blockers.append(f"{locus}: conditional usage has no condition")
        if _unfinished(item.get("classification_rationale")):
            blockers.append(f"{locus}: classification_rationale is missing or placeholder")
        for field in ("condition", "datatype", "value_set_or_binding_ref"):
            value = item.get(field)
            if isinstance(value, str) and _unfinished(value):
                blockers.append(f"{locus}: {field} is blank or placeholder")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            blockers.append(f"{locus}: evidence is missing")
        elif any(_unfinished(value) for value in evidence):
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
    if (
        source_a["errata_artifact_sha256"].lower()
        != source_b["errata_artifact_sha256"].lower()
    ):
        raise ValueError(
            "independent extractions do not use the same errata artifact"
        )
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
        errata_sha256=source_a["errata_artifact_sha256"].lower(),
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
        "errata_sha256": comparison.errata_sha256,
        "extractor_ids": list(comparison.extractor_ids),
        "union_locus_count": comparison.union_locus_count,
        "exact_agreement_count": comparison.exact_agreement_count,
        "exact_agreement_rate": comparison.exact_agreement_rate,
        "missing_from_a": list(comparison.missing_from_a),
        "missing_from_b": list(comparison.missing_from_b),
        "field_disagreements": list(comparison.field_disagreements),
        "adjudication_performed": False,
    }
