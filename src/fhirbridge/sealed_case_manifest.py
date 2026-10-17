"""Readiness and identity helpers for the sealed confirmatory case manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class SealedCaseManifestReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
        and set(value.lower()) != {"0"}
    )


def assess_sealed_case_manifest(
    document: dict[str, Any],
) -> SealedCaseManifestReadiness:
    blockers: list[str] = []

    if document.get("schema_version") != "0.1.0":
        blockers.append("sealed case manifest schema_version is not 0.1.0")
    if document.get("status") != "sealed":
        blockers.append("sealed case manifest status is not sealed")
    if document.get("created_at") is None:
        blockers.append("sealed case manifest has no creation timestamp")
    if document.get("split") != "sealed_test":
        blockers.append("sealed case manifest split is not sealed_test")
    if _placeholder(document.get("manifest_id")):
        blockers.append("sealed case manifest ID is still a placeholder")

    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        blockers.append("sealed case manifest has no cases")
        cases = []

    declared_count = document.get("case_count")
    if (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count < 1
    ):
        blockers.append("sealed case manifest case_count must be positive")
    elif declared_count != len(cases):
        blockers.append("sealed case manifest case_count does not match cases")

    seen_case_ids: set[str] = set()
    for item in cases:
        if not isinstance(item, dict):
            blockers.append("sealed case manifest contains malformed case entry")
            continue
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id or _placeholder(case_id):
            blockers.append("sealed case manifest contains missing/placeholder case_id")
            continue
        if case_id in seen_case_ids:
            blockers.append(f"duplicate sealed case_id: {case_id}")
        seen_case_ids.add(case_id)

        family = item.get("scenario_family")
        if (
            not isinstance(family, str)
            or len(family) != 7
            or not family.startswith("LAB-")
            or not family[4:].isdigit()
        ):
            blockers.append(f"{case_id}: scenario_family is malformed")

        cluster_id = item.get("analysis_cluster_id")
        if (
            not isinstance(cluster_id, str)
            or not cluster_id.strip()
            or _placeholder(cluster_id)
        ):
            blockers.append(
                f"{case_id}: analysis_cluster_id is missing or placeholder"
            )

        if not _valid_sha256(item.get("source_input_sha256")):
            blockers.append(
                f"{case_id}: source_input_sha256 is missing/malformed/placeholder"
            )
        if not _valid_sha256(item.get("canonical_graph_sha256")):
            blockers.append(
                f"{case_id}: canonical_graph_sha256 is missing/malformed/placeholder"
            )

    return SealedCaseManifestReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )


def sealed_case_ids(document: dict[str, Any]) -> set[str]:
    readiness = assess_sealed_case_manifest(document)
    if not readiness.ready:
        raise ValueError(
            "sealed case manifest is not ready: "
            + "; ".join(readiness.blockers)
        )
    return {str(item["case_id"]) for item in document["cases"]}


def source_input_sha256_by_case(
    document: dict[str, Any],
) -> dict[str, str]:
    readiness = assess_sealed_case_manifest(document)
    if not readiness.ready:
        raise ValueError(
            "sealed case manifest is not ready: "
            + "; ".join(readiness.blockers)
        )
    return {
        str(item["case_id"]): str(item["source_input_sha256"]).lower()
        for item in document["cases"]
    }


def analysis_cluster_id_by_case(
    document: dict[str, Any],
) -> dict[str, str]:
    readiness = assess_sealed_case_manifest(document)
    if not readiness.ready:
        raise ValueError(
            "sealed case manifest is not ready: "
            + "; ".join(readiness.blockers)
        )
    return {
        str(item["case_id"]): str(item["analysis_cluster_id"])
        for item in document["cases"]
    }
