"""Re-audit generated blind Edition 5 ZIP before CI publishes artifacts.

This does NOT verify the source PDFs, reviewer independence or any HL7 G1 rule.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fhirbridge.path_b_blind_packet_audit import audit_blind_packet_files

from .build_blind_packet import _MANIFEST, _PACKET, _SCHEMA, _TEMPLATE, _readme

_REPORT = Path(
    "qualification/hl7v2/required_element_review/generated/"
    "lri-edition5-blind-extraction-integrity.json"
)


def main() -> None:
    result = audit_blind_packet_files(
        packet=_PACKET,
        manifest=_MANIFEST,
        expected_payloads={
            "README.txt": _readme().encode("utf-8"),
            "required-element-extraction.schema.json": _SCHEMA.read_bytes(),
            "extraction-template.yaml": _TEMPLATE.read_bytes(),
        },
    )
    report = asdict(result) | {
        "status": result.status,
        "independent_extraction_received": result.independent_extraction_received,
        "official_source_pdfs_verified_or_licensed": (
            result.official_source_pdfs_verified_or_licensed
        ),
        "G1_qualified": result.G1_qualified,
        "external_distribution_authorized": result.external_distribution_authorized,
    }
    _REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
