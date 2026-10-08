"""Summarize pinned FHIR validator logs for reproducible qualification evidence."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SUMMARY = re.compile(
    r"Success:\s*(?P<errors>\d+) errors,\s*"
    r"(?P<warnings>\d+) warnings,\s*"
    r"(?P<notes>\d+) notes"
)


def summarize_log(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = list(_SUMMARY.finditer(text))
    if not matches:
        raise ValueError(f"validator summary not found in {path}")
    match = matches[-1]
    return {
        "file": path.name,
        "errors": int(match.group("errors")),
        "warnings": int(match.group("warnings")),
        "notes": int(match.group("notes")),
    }


def summarize_directory(directory: Path) -> dict[str, object]:
    logs = sorted(directory.glob("LAB-*.log"))
    if not logs:
        raise ValueError(f"no FHIR qualification logs found in {directory}")

    fixtures = [summarize_log(path) for path in logs]
    return {
        "fixture_count": len(fixtures),
        "zero_error_fixture_count": sum(item["errors"] == 0 for item in fixtures),
        "total_errors": sum(int(item["errors"]) for item in fixtures),
        "total_warnings": sum(int(item["warnings"]) for item in fixtures),
        "total_notes": sum(int(item["notes"]) for item in fixtures),
        "fixtures": fixtures,
    }


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "qualification/fhir/results")
    summary = summarize_directory(directory)
    output = directory / "qualification-summary.json"
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if summary["total_errors"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
