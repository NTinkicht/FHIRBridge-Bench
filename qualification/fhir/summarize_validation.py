"""CLI wrapper for FHIR structural qualification summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fhirbridge.fhir_qualification import summarize_directory


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "qualification/fhir/results")
    summary = summarize_directory(directory)
    output = directory / "qualification-summary.json"
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if summary["total_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
