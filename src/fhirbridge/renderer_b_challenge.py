"""Build clean-room Renderer B development challenge inputs.

The challenge contains canonical graphs only. It intentionally excludes Renderer A
source/output, verifier decisions, fault labels, and target serializations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .canonical import generate_lab_scenario

_RENDERER_B_CHALLENGE_VERSION = "0.3.0"
_TEMPLATES = tuple(f"LAB-{index:03d}" for index in range(1, 13))
_SEED_BASE = 15000

# These are exact *payload keys*, not patient/report vocabulary. They must
# never leak source renderer output, reference answers, verifier verdicts,
# fault labels, or sealed-set data into a Codex challenge, even when someone
# extends the canonical generator in the future.
# Namespace/prefix checks supplement exact keys. In particular future
# canonical generators may call the same sensitive concept verifier_results,
# verifier_verdict, verifierOutput, goldLabels or fault_answer; exact-key
# matching alone is inadequate. Do not ban generic "reference_" because
# canonical clinical graphs legitimately contain reference_range.
_FORBIDDEN_KEY_PREFIXES = (
    "renderer_a", "verifier", "gold", "expected_", "fault_",
    "sealed_", "answer_key", "reference_renderer_", "reference_fhir",
    "reference_hl7", "reference_output",
)

_FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "renderer_a", "renderer_a_output", "renderer_a_serialization",
    "renderer_a_reference", "renderer_a_implementation",
    "reference_renderer_output", "reference_fhir", "reference_hl7",
    "gold", "gold_output", "gold_target", "gold_serialization",
    "target_gold_serialization", "target_serialization",
    "expected_output", "expected_outputs", "expected_artifact",
    "expected_fhir", "expected_hl7", "expected_hl7v2", "expected_er7",
    "verifier_decision", "verifier_decisions", "verifier_classification",
    "semantic_verifier_result", "semantic_verifier_decision",
    "fault_label", "fault_labels", "fault_id", "fault_expected_classification",
    "sealed_case", "sealed_set", "sealed_test_data",
    "test_answer", "answer_key",
})


@dataclass(frozen=True)
class RendererBChallengeCase:
    case_id: str
    scenario_id: str
    seed: int
    graph_sha256: str
    primary_endpoint_eligible: bool
    contract_state: str
    graph: dict[str, Any]


def validate_renderer_b_challenge_inputs(
    cases: tuple[RendererBChallengeCase, ...],
) -> None:
    """Fail closed before exporting anything to an isolated coding agent.

    No synthetic development input is sufficient evidence of an independent
    clean-room implementation, but this check catches direct reference-output
    leaks. It rejects unknown/extra scenario IDs and duplicate case/graph
    identities without inspecting either renderer's semantic implementation.
    """
    if not cases or len(cases) != len(_TEMPLATES):
        raise ValueError("Renderer B handoff requires exactly 12 development cases")
    if {case.scenario_id for case in cases} != set(_TEMPLATES):
        raise ValueError("Renderer B handoff has missing or extra scenarios")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Renderer B handoff has duplicate case IDs")
    if len({case.graph_sha256 for case in cases}) != len(cases):
        raise ValueError("Renderer B handoff repeats a canonical graph")

    def visit(value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError("Renderer B graph has a non-string key")
                # Match snake_case, kebab-case and CamelCase labels.
                # Physical clinical fields such as reference_range and
                # target_fact_id must remain legal canonical inputs.
                snake = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", key)
                normalized = re.sub(
                    r"(?<=[a-z0-9])(?=[A-Z])", "_", snake
                ).casefold().replace("-", "_").replace(" ", "_")
                # Match sensitive *tokens* anywhere in compound names. Bare
                # substring matching would falsely reject default or
                # unexpected_status; clinical reference_range is also valid.
                tokens = set(normalized.split("_"))
                sensitive_concepts = {
                    "renderer", "verifier", "fault", "gold",
                    "expected", "sealed", "answer", "oracle",
                }
                if (
                    normalized in _FORBIDDEN_PAYLOAD_KEYS
                    or normalized.startswith(_FORBIDDEN_KEY_PREFIXES)
                    or bool(tokens & sensitive_concepts)
                ):
                    raise ValueError(
                        "Renderer B challenge contains prohibited reference "
                        f"or answer field at {path}.{key}"
                    )
                visit(child, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path=f"{path}[{index}]")

    for case in cases:
        if not isinstance(case.graph, dict):
            raise ValueError("Renderer B challenge graph must be a mapping")
        if "assertions" in case.graph:
            raise ValueError("Renderer B handoff must not include test assertions")
        metadata = case.graph.get("scenario_metadata")
        if not isinstance(metadata, dict) or (
            metadata.get("partition") != "development"
            or metadata.get("synthetic_only") is not True
        ):
            raise ValueError("Renderer B handoff may contain synthetic development data only")
        if case.graph_sha256 != _document_sha256(case.graph):
            raise ValueError("Renderer B handoff graph hash no longer matches its payload")
        visit(case.graph, path=case.case_id)


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
        # The internal canonical generator embeds test assertions including
        # expected values/units. Those are developer-oracle hints, not graph
        # facts: never pass them to the isolated Codex implementation. Remove
        # them *before* hashing and exporting the sanitized challenge.
        graph.pop("assertions", None)
        # Scenario-level expected rule IDs are grading hints, not facts.
        # Codex must derive applicable projection from contract/standards,
        # never from a precomputed answer list.
        graph["scenario_metadata"].pop("expected_rule_ids", None)
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
    result = tuple(cases)
    validate_renderer_b_challenge_inputs(result)
    return result


def challenge_manifest(
    cases: tuple[RendererBChallengeCase, ...],
) -> dict[str, Any]:
    """Return metadata for a checked clean-room challenge, not a scientific proof."""

    validate_renderer_b_challenge_inputs(cases)
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
    # Preflight **all** cases before creating a single output file.
    validate_renderer_b_challenge_inputs(cases)
    manifest = challenge_manifest(cases)
    inputs = output_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    for case in cases:
        path = inputs / f"{case.case_id}.json"
        path.write_text(
            json.dumps(case.graph, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
