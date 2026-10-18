"""Verify the coordinator's local Edition 5 guide and errata PDF bytes.

Run: python qualification/hl7v2/required_element_review/verify_source_documents.py
     /path/to/edition5.pdf /path/to/errata.pdf
The PDFs themselves are never copied or uploaded by this command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fhirbridge.lri_source_identity import verify_publication_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("guide_pdf", type=Path)
    parser.add_argument("errata_pdf", type=Path)
    args = parser.parse_args()
    try:
        result = verify_publication_files(args.guide_pdf, args.errata_pdf)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "SOURCE_VERIFICATION_FAILED", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
