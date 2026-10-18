"""Validate a returned clean-room Renderer B implementation declaration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fhirbridge.renderer_b_submission import (
    assess_renderer_b_declaration,
    renderer_b_readiness_to_dict,
)
from fhirbridge.schema_validation import load_yaml, require_valid_document

_SCHEMA = Path(
    "renderer_validation/schema/renderer_implementation_declaration.schema.json"
)
_EXPECTED_SCHEMA = Path(
    "renderer_validation/schema/renderer_b_expected_inputs.schema.json"
)
_DEFAULT_OUTPUT = Path(
    "renderer_validation/results/renderer-b-submission-readiness.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Renderer B's implementation declaration and enforce "
            "clean-room comparison gates."
        )
    )
    parser.add_argument("declaration", type=Path)
    parser.add_argument(
        "--expected-inputs",
        type=Path,
        required=True,
        help="Custodian-side clean-room handoff record.",
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    require_valid_document(args.declaration, _SCHEMA)
    declaration = load_yaml(args.declaration)
    require_valid_document(args.expected_inputs, _EXPECTED_SCHEMA)
    expected = load_yaml(args.expected_inputs)["clean_room_inputs"]

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=expected,
    )
    report = renderer_b_readiness_to_dict(readiness)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if readiness.ready_for_differential_comparison else 2


if __name__ == "__main__":
    raise SystemExit(main())
