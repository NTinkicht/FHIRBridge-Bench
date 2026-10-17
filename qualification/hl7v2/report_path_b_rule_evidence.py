"""Emit a prefreeze Path B rule evidence report, never a scientific G1 pass."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from fhirbridge.path_b_rule_evidence import assess_path_b_rule_evidence

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (
    ROOT
    / "qualification/hl7v2/required_element_review/examples/"
    "path_b_rule_evidence_dev_template.json"
)
COVERAGE = ROOT / "benchmark/path_b_bounded_coverage.yaml"
FREEZE = ROOT / "benchmark/protocol_freeze_gates.yaml"
OUTPUT = ROOT / "qualification/hl7v2/results/path-b-rule-evidence-prefreeze.json"


def main() -> None:
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    report = assess_path_b_rule_evidence(
        document, coverage=coverage, protocol_gates=freeze
    )
    payload = asdict(report)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
