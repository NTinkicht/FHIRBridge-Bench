"""Command-line utilities for validating versioned FHIRBridge research artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .schema_validation import validate_document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fhirbridge-validate",
        description="Validate a YAML research artifact against a JSON Schema.",
    )
    parser.add_argument("artifact", type=Path, help="YAML artifact to validate")
    parser.add_argument("schema", type=Path, help="JSON-Schema/YAML schema")
    parser.add_argument(
        "--schema-dir",
        dest="schema_dirs",
        action="append",
        type=Path,
        default=[],
        help="Additional local schema directory; may be repeated",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    problems = validate_document(
        args.artifact,
        args.schema,
        extra_schema_directories=args.schema_dirs,
    )

    if problems:
        print(f"FAIL {args.artifact}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"PASS {args.artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
