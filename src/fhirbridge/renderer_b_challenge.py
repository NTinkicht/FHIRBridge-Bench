"""Build clean-room Renderer B development challenge inputs.

The challenge contains canonical graphs only. It intentionally excludes Renderer A
source/output, verifier decisions, fault labels, and target serializations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .canonical import generate_lab_scenario

_RENDERER_B_CHALLENGE_VERSION = "0.2.0"
_TEMPLATES = tuple(f"LAB-{index:03d}" for index in range(1, 13))
_SEED_BASE = 15000


@dataclass(frozen=True)
class RendererBChallengeCase:
    case_id: str
    scenario_id: str
    seed: int
    graph_sha256: str
    primary_endpoint_eligible: bool
    contract_state: str
    graph: dict[str, Any]


def _document_sha256(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_renderer_b_challenge() -> tuple[RendererBChallengeCase, ...]:
    """Return one deterministic development case per first-slice scenario."""

    cases: list[RendererBChallengeCase] = []
    for offset, scenario_id in enumerate(_TEMPLATES):
        seed = _SEED_BASE + offset
        graph = generate_lab_scenario(
            scenario_id,
            seed,
            partition="development",
            include_order_context=True,
        )
        metadata = graph["scenario_metadata"]
        cases.append(
            RendererBChallengeCase(
                case_id=f"RB-{offset + 1:03d}",
                scenario_id=scenario_id,
                seed=seed,
                graph_sha256=_document_sha256(graph),
                primary_endpoint_eligible=bool(
                    metadata["primary_endpoint_eligible"]
                ),
                contract_state=str(metadata["contract_state"]),
                graph=graph,
            )
        )
    return tuple(cases)


def challenge_manifest(
    cases: tuple[RendererBChallengeCase, ...],
) -> dict[str, Any]:
    """Return metadata that proves the clean-room challenge has no target gold."""

    payload = {
        "challenge_id": "FHIRBRIDGE-RENDERER-B-DEV-001",
        "version": _RENDERER_B_CHALLENGE_VERSION,
        "partition": "development",
        "contains_renderer_a_output": False,
        "contains_target_gold_serialization": False,
        "contains_verifier_decisions": False,
        "contains_fault_labels": False,
        "contains_order_context": True,
        "hl7v2_order_projection_policy": (
            "fail_closed_until_exact_edition5_machine_profile_and_external_review"
        ),
        "contract": {
            "path": "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml",
            "version": "0.3.0",
            "freeze_status": "draft_not_frozen",
        },
        "cases": [
            {
                "case_id": case.case_id,
                "scenario_id": case.scenario_id,
                "seed": case.seed,
                "graph_sha256": case.graph_sha256,
                "primary_endpoint_eligible": case.primary_endpoint_eligible,
                "contract_state": case.contract_state,
                "input_path": f"inputs/{case.case_id}.json",
            }
            for case in cases
        ],
    }
    payload["manifest_sha256"] = _document_sha256(payload)
    return payload


def write_renderer_b_challenge(output_dir: Path) -> dict[str, Any]:
    cases = build_renderer_b_challenge()
    inputs = output_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    for case in cases:
        path = inputs / f"{case.case_id}.json"
        path.write_text(
            json.dumps(case.graph, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    manifest = challenge_manifest(cases)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
