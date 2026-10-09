"""Write the current dependency/tooling freeze-readiness report."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from fhirbridge.tooling_manifest import (
    assess_freeze_readiness,
    freeze_readiness_to_dict,
)

_MANIFEST = Path("benchmark/tooling_versions.yaml")


def main() -> int:
    with _MANIFEST.open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)

    readiness = assess_freeze_readiness(manifest)
    report = freeze_readiness_to_dict(readiness)

    output_dir = Path("qualification/freeze/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "tooling-freeze-readiness.json"
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
