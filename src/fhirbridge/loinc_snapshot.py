"""Qualification helpers for a local, licensed LOINC CSV snapshot."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LoincRequiredCode:
    code: str
    expected_status: str
    expected_long_common_name: str
    benchmark_role: str


@dataclass(frozen=True)
class LoincQualificationResult:
    code: str
    present: bool
    status_match: bool
    name_match: bool
    observed_status: str | None
    observed_long_common_name: str | None

    @property
    def passed(self) -> bool:
        return self.present and self.status_match and self.name_match


@dataclass(frozen=True)
class LoincQualificationReport:
    version: str
    total_required: int
    passed_required: int
    all_passed: bool
    results: tuple[LoincQualificationResult, ...]


def load_required_codes(path: Path) -> tuple[str, tuple[LoincRequiredCode, ...]]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    snapshot = document.get("snapshot") if isinstance(document, dict) else None
    required = document.get("required_codes") if isinstance(document, dict) else None
    if not isinstance(snapshot, dict):
        raise ValueError("LOINC requirements must contain snapshot metadata")
    version = snapshot.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("snapshot.version must be a non-empty string")
    if not isinstance(required, list) or not required:
        raise ValueError("LOINC requirements must contain required_codes")

    parsed: list[LoincRequiredCode] = []
    seen: set[str] = set()
    for index, item in enumerate(required):
        if not isinstance(item, dict):
            raise ValueError(f"required_codes[{index}] must be a mapping")
        code = item.get("code")
        status = item.get("expected_status")
        name = item.get("expected_long_common_name")
        role = item.get("benchmark_role")
        if not all(isinstance(value, str) and value for value in (code, status, name, role)):
            raise ValueError(f"required_codes[{index}] has missing string fields")
        if code in seen:
            raise ValueError(f"duplicate required LOINC code: {code}")
        seen.add(code)
        parsed.append(
            LoincRequiredCode(
                code=code,
                expected_status=status,
                expected_long_common_name=name,
                benchmark_role=role,
            )
        )

    return version, tuple(parsed)


def _load_loinc_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"LOINC CSV is not a file: {path}")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"LOINC_NUM", "STATUS", "LONG_COMMON_NAME"}
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(required_columns - fieldnames)
        if missing:
            raise ValueError(
                "LOINC CSV missing required columns: " + ", ".join(missing)
            )
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            code = row.get("LOINC_NUM")
            if isinstance(code, str) and code:
                rows[code] = row
    return rows


def qualify_loinc_snapshot(
    loinc_csv: Path,
    requirements_path: Path,
) -> LoincQualificationReport:
    version, required_codes = load_required_codes(requirements_path)
    rows = _load_loinc_rows(loinc_csv)

    results: list[LoincQualificationResult] = []
    for requirement in required_codes:
        row = rows.get(requirement.code)
        observed_status = row.get("STATUS") if row else None
        observed_name = row.get("LONG_COMMON_NAME") if row else None
        present = row is not None
        results.append(
            LoincQualificationResult(
                code=requirement.code,
                present=present,
                status_match=(
                    present and observed_status == requirement.expected_status
                ),
                name_match=(
                    present
                    and observed_name == requirement.expected_long_common_name
                ),
                observed_status=observed_status,
                observed_long_common_name=observed_name,
            )
        )

    passed = sum(item.passed for item in results)
    return LoincQualificationReport(
        version=version,
        total_required=len(results),
        passed_required=passed,
        all_passed=passed == len(results),
        results=tuple(results),
    )


def qualification_to_dict(report: LoincQualificationReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "total_required": report.total_required,
        "passed_required": report.passed_required,
        "all_passed": report.all_passed,
        "results": [
            {
                "code": item.code,
                "present": item.present,
                "status_match": item.status_match,
                "name_match": item.name_match,
                "observed_status": item.observed_status,
                "observed_long_common_name": item.observed_long_common_name,
            }
            for item in report.results
        ],
    }
