"""Fail-closed readiness checks for the Edition 5 required-element inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequiredElementInventoryReadiness:
    ready: bool
    blockers: tuple[str, ...]


def assess_required_element_inventory(document: dict[str, Any]) -> RequiredElementInventoryReadiness:
    inventory = document.get("inventory")
    extraction = document.get("extraction_protocol")
    completion = document.get("completion_gate")
    if not isinstance(inventory, dict):
        raise ValueError("required-element inventory metadata is missing")
    if not isinstance(extraction, dict):
        raise ValueError("extraction_protocol is missing")
    if not isinstance(completion, dict):
        raise ValueError("completion_gate is missing")

    blockers: list[str] = []
    if inventory.get("status") != "complete":
        blockers.append("inventory.status is not complete")

    for reader_name in ("reader_a", "reader_b"):
        reader = extraction.get(reader_name)
        if not isinstance(reader, dict) or reader.get("status") != "complete":
            blockers.append(f"{reader_name} independent extraction is incomplete")

    if extraction.get("agreement_required") is not True:
        blockers.append("independent extraction agreement is not required")

    unresolved = document.get("unresolved_inventory_domains")
    if not isinstance(unresolved, list):
        raise ValueError("unresolved_inventory_domains must be a list")
    if unresolved:
        blockers.append(
            f"{len(unresolved)} required-element inventory domains remain unresolved"
        )

    questions = document.get("specific_questions_from_hostile_review", [])
    if not isinstance(questions, list):
        raise ValueError("specific_questions_from_hostile_review must be a list")
    unresolved_questions = [
        item.get("question_id", "unknown")
        for item in questions
        if isinstance(item, dict) and item.get("status") != "resolved"
    ]
    if unresolved_questions:
        blockers.append(
            "hostile-review inventory questions remain unresolved: "
            + ", ".join(sorted(map(str, unresolved_questions)))
        )

    machine = document.get("authoritative_sources", {}).get(
        "machine_readable_edition5_bundle", {}
    )
    if not isinstance(machine, dict) or machine.get("status") != "reconciled":
        blockers.append("exact machine-readable Edition 5 bundle is not reconciled")

    ready = not blockers
    if inventory.get("status") == "complete" and not ready:
        raise ValueError(
            "inventory cannot be marked complete while readiness blockers remain: "
            + "; ".join(blockers)
        )
    return RequiredElementInventoryReadiness(
        ready=ready,
        blockers=tuple(sorted(set(blockers))),
    )
