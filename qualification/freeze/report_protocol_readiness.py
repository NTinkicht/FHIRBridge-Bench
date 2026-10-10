"""Write overall protocol-freeze readiness, not just tooling readiness."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from fhirbridge.analysis_design_consistency import (
    assess_analysis_design_consistency,
)
from fhirbridge.tooling_manifest import assess_freeze_readiness

_TOOLING = Path("benchmark/tooling_versions.yaml")
_PROTOCOL_GATES = Path("benchmark/protocol_freeze_gates.yaml")
_OUTPUT = Path("qualification/freeze/results/protocol-freeze-readiness.json")
_CORE_DESIGN = Path("analysis/core_confirmatory_design.yaml")
_ANALYSIS_TEMPLATE = Path(
    "analysis/examples/analysis_preregistration_template.yaml"
)
_SAMPLE_SIZE_METHOD = Path("analysis/sample_size_method.yaml")
_EXECUTION_POLICY = Path("models/execution_policy.yaml")


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def build_report() -> dict:
    tooling = assess_freeze_readiness(_load(_TOOLING))
    design_consistency = assess_analysis_design_consistency(
        _load(_CORE_DESIGN),
        _load(_ANALYSIS_TEMPLATE),
        _load(_SAMPLE_SIZE_METHOD),
        _load(_EXECUTION_POLICY),
    )
    gates_doc = _load(_PROTOCOL_GATES)
    gates = gates_doc.get("gates")
    if not isinstance(gates, list):
        raise ValueError("protocol freeze gate ledger must contain a gates list")

    protocol_blockers: list[dict[str, object]] = []
    for gate in gates:
        if not isinstance(gate, dict):
            raise ValueError("each protocol gate must be an object")
        gate_id = gate.get("gate_id")
        status = gate.get("status")
        if not isinstance(gate_id, str) or not gate_id:
            raise ValueError("each protocol gate requires gate_id")
        if status not in {"blocked", "passed"}:
            raise ValueError(f"unsupported status for {gate_id}: {status!r}")
        if status != "passed":
            blockers = gate.get("blockers", [])
            if not isinstance(blockers, list):
                raise ValueError(f"{gate_id}.blockers must be a list")
            protocol_blockers.append(
                {
                    "gate_id": gate_id,
                    "category": gate.get("category"),
                    "blockers": blockers,
                    "completion_rule": gate.get("completion_rule"),
                }
            )

    protocol_blocker_item_count = sum(
        len(gate["blockers"])
        for gate in protocol_blockers
        if isinstance(gate.get("blockers"), list)
    )
    blocker_items_by_gate = {
        str(gate["gate_id"]): list(gate["blockers"])
        for gate in protocol_blockers
        if isinstance(gate.get("blockers"), list)
    }

    tooling_blockers = [
        *tooling.unresolved_paths,
        *tooling.false_boolean_paths,
    ]
    ready = (
        tooling.ready
        and tooling.manifest_status == "frozen"
        and design_consistency.consistent
        and not protocol_blockers
    )
    return {
        "ready_for_confirmatory_inference": ready,
        "tooling": {
            "ready": tooling.ready,
            "manifest_status": tooling.manifest_status,
            "blocker_count": len(tooling_blockers),
            "blockers": tooling_blockers,
        },
        "implementation_consistency": {
            "ready": design_consistency.consistent,
            "blocker_count": len(design_consistency.blockers),
            "blockers": list(design_consistency.blockers),
        },
        "protocol_non_tooling": {
            "ready": not protocol_blockers,
            "gate_blocker_count": len(protocol_blockers),
            "blocker_item_count": protocol_blocker_item_count,
            "blocker_items_by_gate": blocker_items_by_gate,
            "gates": protocol_blockers,
        },
        "total_blocking_categories": (
            (1 if tooling_blockers or tooling.manifest_status != "frozen" else 0)
            + (0 if design_consistency.consistent else 1)
            + len(protocol_blockers)
        ),
        "interpretation": (
            "Tooling blocker count is not an overall protocol-readiness count."
        ),
    }


def main() -> int:
    report = build_report()
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
