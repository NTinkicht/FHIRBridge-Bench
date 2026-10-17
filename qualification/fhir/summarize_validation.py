"""CLI wrapper for FHIR structural qualification summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fhirbridge.fhir_qualification import summarize_directory
from fhirbridge.fhir_warning_audit import (
    audit_to_dict,
    audit_warning_log_directories,
)


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "qualification/fhir/results")
    summary = summarize_directory(directory)
    order_context_directory = Path("qualification/fhir/order-context")
    evidence_directories = [directory]
    order_context_summary: dict[str, object] | None = None
    if order_context_directory.is_dir():
        order_context_summary = summarize_directory(order_context_directory)
        evidence_directories.append(order_context_directory)

    warning_audit = audit_warning_log_directories(
        evidence_directories,
        Path("benchmark/fhir_validator_warning_policy.yaml"),
    )
    summary["warning_audit"] = audit_to_dict(warning_audit)
    summary["order_context"] = order_context_summary
    output = directory / "qualification-summary.json"
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if summary["total_errors"] != 0:
        return 1
    if (
        isinstance(order_context_summary, dict)
        and order_context_summary["total_errors"] != 0
    ):
        return 1
    if warning_audit.unknown_warnings != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
