"""CLI for qualifying a locally downloaded official LOINC release."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fhirbridge.loinc_release import qualify_loinc_release_zip

_REQUIREMENTS = Path("benchmark/loinc_2_83_snapshot_requirements.yaml")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python qualification/loinc/qualify_release.py /path/to/Loinc_2.83.zip")
        return 2

    archive = Path(sys.argv[1])
    result = qualify_loinc_release_zip(archive, _REQUIREMENTS)
    output_dir = Path("qualification/loinc/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "loinc-2.83-qualification.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["qualification"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
