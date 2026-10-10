"""Classify external FHIR validator warnings against a frozen review policy."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class WarningClassification:
    line: str
    category_id: str | None


@dataclass(frozen=True)
class WarningAudit:
    total_warnings: int
    unknown_warnings: int
    category_counts: dict[str, int]
    classifications: tuple[WarningClassification, ...]


def _warning_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = _ANSI.sub("", raw_line).strip()
        if line.startswith("Warning @ "):
            lines.append(line)
    return lines


def load_warning_policy(path: Path) -> list[tuple[str, re.Pattern[str]]]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    categories = document.get("categories") if isinstance(document, dict) else None
    if not isinstance(categories, list) or not categories:
        raise ValueError("warning policy must define at least one category")

    compiled: list[tuple[str, re.Pattern[str]]] = []
    seen: set[str] = set()
    for item in categories:
        if not isinstance(item, dict):
            raise ValueError("warning policy category must be a mapping")
        category_id = item.get("category_id")
        pattern = item.get("regex")
        if not isinstance(category_id, str) or not category_id:
            raise ValueError("category_id must be a non-empty string")
        if category_id in seen:
            raise ValueError(f"duplicate warning category_id: {category_id}")
        seen.add(category_id)
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{category_id} regex must be a non-empty string")
        compiled.append((category_id, re.compile(pattern)))
    return compiled


def audit_warning_log(
    log_path: Path,
    policy_path: Path,
) -> WarningAudit:
    """Audit one archived validator log against the warning policy."""

    policy = load_warning_policy(policy_path)
    classifications: list[WarningClassification] = []
    counts: Counter[str] = Counter()

    for line in _warning_lines(log_path):
        matched = [
            category_id
            for category_id, pattern in policy
            if pattern.search(line)
        ]
        if len(matched) > 1:
            raise ValueError(
                "FHIR warning matched multiple policy categories: "
                f"{matched}: {line}"
            )
        category_id = matched[0] if matched else None
        if category_id is not None:
            counts[category_id] += 1
        classifications.append(
            WarningClassification(
                line=line,
                category_id=category_id,
            )
        )

    unknown = sum(item.category_id is None for item in classifications)
    return WarningAudit(
        total_warnings=len(classifications),
        unknown_warnings=unknown,
        category_counts=dict(sorted(counts.items())),
        classifications=tuple(classifications),
    )


def audit_warning_logs(
    log_directory: Path,
    policy_path: Path,
) -> WarningAudit:
    classifications: list[WarningClassification] = []
    counts: Counter[str] = Counter()
    unknown = 0

    for path in sorted(log_directory.glob("LAB-*.log")):
        audit = audit_warning_log(path, policy_path)
        classifications.extend(audit.classifications)
        counts.update(audit.category_counts)
        unknown += audit.unknown_warnings

    return WarningAudit(
        total_warnings=len(classifications),
        unknown_warnings=unknown,
        category_counts=dict(sorted(counts.items())),
        classifications=tuple(classifications),
    )


def audit_warning_log_directories(
    log_directories: list[Path] | tuple[Path, ...],
    policy_path: Path,
) -> WarningAudit:
    """Audit several validator-log directories as one evidence set."""

    combined: list[WarningClassification] = []
    counts: Counter[str] = Counter()
    total = 0
    unknown = 0
    for directory in log_directories:
        audit = audit_warning_logs(directory, policy_path)
        total += audit.total_warnings
        unknown += audit.unknown_warnings
        counts.update(audit.category_counts)
        combined.extend(audit.classifications)
    return WarningAudit(
        total_warnings=total,
        unknown_warnings=unknown,
        category_counts=dict(sorted(counts.items())),
        classifications=tuple(combined),
    )


def audit_to_dict(audit: WarningAudit) -> dict[str, Any]:
    return {
        "total_warnings": audit.total_warnings,
        "unknown_warnings": audit.unknown_warnings,
        "category_counts": audit.category_counts,
        "classifications": [
            {
                "category_id": item.category_id,
                "line": item.line,
            }
            for item in audit.classifications
        ],
    }
