"""Private, unadjudicated third-reader source-census triage for Path B.

The first two locked extractions reveal only their observed union. A separately
submitted source census can flag candidate R/C loci both omitted, but neither
the third reader's independence nor the census' completeness can be verified
by software. Never use this module to set G1 or protocol freeze gates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fhirbridge.lri_adjudication_handoff import build_adjudication_handoff
from fhirbridge.lri_source_identity import pinned_publication_hashes

_CENSUS_AREAS = (
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
_RULE_ID = re.compile(r"^CEN-[A-Z0-9-]+$")
_AREA_SET = frozenset(_CENSUS_AREAS)


@dataclass(frozen=True)
class SourceCensusTriage:
    census_candidate_rule_count: int
    observed_first_two_reader_locus_count: int
    candidate_rule_ids_missing_from_both: tuple[str, ...]
    candidate_loci_missing_from_both: tuple[str, ...]
    same_locus_rule_ids_requiring_source_comparison: tuple[str, ...]
    unreviewed_source_areas: tuple[str, ...]
    census_reviewer_id: str

    @property
    def status(self) -> str:
        return "PRIVATE_SOURCE_CENSUS_CANDIDATE_TRIAGE_ONLY"

    @property
    def independently_established_requirements_denominator(self) -> None:
        return None

    @property
    def standards_completeness_certified(self) -> bool:
        return False

    @property
    def human_adjudication_performed(self) -> bool:
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


def _pages(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(type(page) is int and page > 0 for page in value)
        and len(set(value)) == len(value)
    )


def _check_census(census: dict[str, Any], *, extractors: list[str]) -> dict[str, str]:
    if not isinstance(census, dict) or set(census) != {
        "schema_version", "status", "census_reviewer_id",
        "source_sha256", "errata_sha256", "scope_areas", "candidate_requirements",
    }:
        raise ValueError("source census format is incomplete or contains unsupported keys")
    identity = census["census_reviewer_id"]
    if (
        census["schema_version"] != "0.1.0"
        or census["status"] != "UNADJUDICATED_SOURCE_CENSUS_DRAFT"
        or type(identity) is not str
        or not identity.strip()
        or identity.upper().startswith(("TO_BE_", "TBD", "TEST-UNKNOWN"))
        or identity in extractors
    ):
        raise ValueError("source census status or independent reviewer identity invalid")
    pinned = pinned_publication_hashes()
    if (
        census["source_sha256"] != pinned["implementation_guide"]
        or census["errata_sha256"] != pinned["errata_letter"]
    ):
        raise ValueError("source census must identify the pinned guide and errata")

    areas = census["scope_areas"]
    if not isinstance(areas, list) or len(areas) != len(_CENSUS_AREAS):
        raise ValueError("source census must enumerate every bounded scope area")
    area_status: dict[str, str] = {}
    for area in areas:
        if not isinstance(area, dict) or set(area) != {
            "coverage_area", "status", "source_pages",
        }:
            raise ValueError("source census coverage item has invalid fields")
        key, status, pages = (
            area["coverage_area"], area["status"], area["source_pages"]
        )
        if (
            type(key) is not str
            or key not in _AREA_SET
            or key in area_status
            or status not in ("UNREVIEWED", "SOURCE_PAGES_CHECKED")
            or (status == "UNREVIEWED" and pages != [])
            or (status == "SOURCE_PAGES_CHECKED" and not _pages(pages))
        ):
            raise ValueError("source census coverage item is duplicate, invalid or unsupported")
        area_status[key] = status
    if set(area_status) != _AREA_SET:
        raise ValueError("source census must include all bounded scope areas")
    return area_status


def audit_candidate_source_census(
    *,
    raw_a: bytes,
    lock_a: dict[str, Any],
    raw_b: bytes,
    lock_b: dict[str, Any],
    census: dict[str, Any],
) -> SourceCensusTriage:
    """Triages candidate third-source omissions against *locked original bytes*.

    An observed locus does not prove an identical R/C requirement was found:
    multiple distinct source predicates may apply to the same HL7 field.
    Every same-locus match is therefore still listed for human comparison.
    """
    handoff = build_adjudication_handoff(raw_a, lock_a, raw_b, lock_b)
    status_by_area = _check_census(
        census, extractors=handoff["extractor_ids"]
    )
    candidates = census["candidate_requirements"]
    if not isinstance(candidates, list):
        raise ValueError("source census candidates must be a list")
    unique_ids: set[str] = set()
    absent_ids: list[str] = []
    absent_loci: set[str] = set()
    same_locus_ids: list[str] = []
    observed = {row["locus"] for row in handoff["adjudication_rows"]}
    for item in candidates:
        if not isinstance(item, dict) or set(item) != {
            "census_rule_id", "locus", "usage", "condition", "coverage_area", "source_pages",
        }:
            raise ValueError("invalid candidate source requirement fields")
        identifier = item["census_rule_id"]
        locus = item["locus"]
        area = item["coverage_area"]
        usage = item["usage"]
        condition = item["condition"]
        if (
            type(identifier) is not str
            or _RULE_ID.fullmatch(identifier) is None
            or identifier in unique_ids
            or type(locus) is not str
            or not locus.strip()
            or type(area) is not str
            or status_by_area.get(area) != "SOURCE_PAGES_CHECKED"
            or usage not in ("R", "C")
            or (usage == "C" and (type(condition) is not str or not condition.strip()))
            or (usage == "R" and condition is not None)
            or not _pages(item["source_pages"])
        ):
            raise ValueError("candidate source requirement is invalid or unsupported")
        unique_ids.add(identifier)
        if locus in observed:
            same_locus_ids.append(identifier)
        else:
            absent_ids.append(identifier)
            absent_loci.add(locus)

    return SourceCensusTriage(
        census_candidate_rule_count=len(candidates),
        observed_first_two_reader_locus_count=len(observed),
        candidate_rule_ids_missing_from_both=tuple(sorted(absent_ids)),
        candidate_loci_missing_from_both=tuple(sorted(absent_loci)),
        same_locus_rule_ids_requiring_source_comparison=tuple(sorted(same_locus_ids)),
        unreviewed_source_areas=tuple(sorted(
            area for area, status in status_by_area.items() if status == "UNREVIEWED"
        )),
        census_reviewer_id=census["census_reviewer_id"],
    )
