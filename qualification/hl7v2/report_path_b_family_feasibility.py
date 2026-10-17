"""Write a reproducible 11-family Path B DEVELOPMENT feasibility report.

It never marks G1 qualified or gives confirmatory permission. Run in the
repository checkout after installing the editable research package.
"""

from __future__ import annotations

import json
from pathlib import Path

from fhirbridge.path_b_development_feasibility import build_development_feasibility

_OUTPUT = Path("qualification/hl7v2/results/path-b-11-family-prefreeze.json")


def main() -> int:
    report = build_development_feasibility()
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report_file": str(_OUTPUT),
                "status": report["status"],
                "primary_family_count": report["primary_family_count"],
                "fhir_draft_roundtrip_count": (
                    report["development_fhir_roundtrip_draft_faithful_count"]
                ),
                "hl7v2_fail_closed_count": (
                    report["hl7v2_order_renderer_fail_closed_count"]
                ),
                "independent_G1_qualified_family_count": 0,
                "confirmatory_permission": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
