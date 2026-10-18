"""Standalone, allowlisted Codex exploratory Renderer B custody/identity gate.

This clean-room variant deliberately imports NO Renderer A, canonical generator,
semantic verifier, lifter, or scientific mapping code. Development only.
"""
from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
SCHEMAS = ROOT / "renderer_validation" / "schema"
SENSITIVE = (
    "renderer_a", "verifier", "gold", "expected_", "fault_", "sealed_",
    "answer_key", "reference_renderer_", "reference_fhir", "reference_hl7",
    "reference_output",
)
SENSITIVE_EXACT = frozenset({
    "target_gold_serialization", "target_serialization", "test_answer",
    "semantic_verifier_result", "semantic_verifier_decision",
    "reference_renderer_output",
})


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def validate_document(data: Any, name: str, schema_name: str, errors: list[str]) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for problem in validator.iter_errors(data):
        errors.append(f"{name} schema {problem.json_path}: {problem.message}")


def check_graph(graph: Any, case_id: str, errors: list[str]) -> None:
    if not isinstance(graph, dict):
        errors.append(f"{case_id}: not a graph object")
        return
    metadata = graph.get("scenario_metadata", {})
    if "assertions" in graph or (isinstance(metadata, dict) and "expected_rule_ids" in metadata):
        errors.append(f"{case_id}: leaked developer answer assertions/rule IDs")
    if not isinstance(metadata, dict) or metadata.get("partition") != "development" or metadata.get("synthetic_only") is not True:
        errors.append(f"{case_id}: not a synthetic development graph")

    def walk(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    errors.append(f"{location}: non-string graph key")
                    continue
                normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
                normalized = normalized.casefold().replace("-", "_").replace(" ", "_")
                # Compound namespaces must not bypass a leading-name denylist:
                # semanticVerifierClassification, seededFaultLabel, and
                # sourceRendererAOutput are sensitive even with neutral prefixes.
                # Avoid banning reference_range, a legitimate canonical field.
                sensitive_concepts = (
                    "renderer", "verifier", "fault", "gold", "expected",
                    "sealed", "answer", "oracle",
                )
                if (
                    normalized.startswith(SENSITIVE)
                    or normalized in SENSITIVE_EXACT
                    or any(concept in normalized for concept in sensitive_concepts)
                ):
                    errors.append(f"{location}.{key}: prohibited reference/output field")
                walk(child, f"{location}.{key}")
        elif isinstance(value, list):
            for n, child in enumerate(value):
                walk(child, f"{location}[{n}]")
    walk(graph, case_id)


def assess(declaration_file: Path, expected_file: Path, challenge_dir: Path) -> dict:
    errors: list[str] = []
    declaration = yaml.safe_load(declaration_file.read_text(encoding="utf-8"))
    expected = yaml.safe_load(expected_file.read_text(encoding="utf-8"))
    validate_document(declaration, "declaration", "renderer_implementation_declaration.schema.json", errors)
    validate_document(expected, "custodian", "renderer_b_expected_inputs.schema.json", errors)

    inputs = expected.get("clean_room_inputs", {}) if isinstance(expected, dict) else {}
    attested = declaration.get("clean_room_inputs", {}) if isinstance(declaration, dict) else {}
    fields = (
        "repository_full_name", "branch", "starting_commit", "challenge_id",
        "challenge_version", "challenge_manifest_sha256", "contract_path",
        "contract_sha256",
    )
    for field in fields:
        if inputs.get(field) != attested.get(field):
            errors.append(f"declaration.clean_room_inputs.{field}: custodian mismatch")

    if inputs.get("branch") != "renderer-b-cleanroom" or inputs.get("challenge_version") != "0.3.0":
        errors.append("not the permitted clean-room branch / sanitized v0.3.0 challenge")
    if inputs.get("contract_path") != CONTRACT:
        errors.append("custodian identifies the wrong contract path")
    starting = inputs.get("starting_commit", "")
    if not isinstance(starting, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", starting) or set(starting.lower()) <= {"0"}:
        errors.append("invalid clean-room starting commit")

    contract = ROOT / CONTRACT
    if not contract.exists() or sha256(contract.read_bytes()).hexdigest() != inputs.get("contract_sha256"):
        errors.append("custodian contract SHA-256 disagrees with actual allowlisted file")

    manifest_file = challenge_dir / "manifest.json"
    if not manifest_file.is_file():
        errors.append("canonical challenge manifest missing")
    else:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        actual_hash = manifest.get("manifest_sha256", "")
        if (
            manifest.get("challenge_id") != "FHIRBRIDGE-RENDERER-B-DEV-001"
            or manifest.get("challenge_id") != inputs.get("challenge_id")
        ):
            errors.append("challenge manifest ID disagrees with the custody record")
        if manifest.get("version") != "0.3.0" or manifest.get("partition") != "development":
            errors.append("challenge version/partition mismatch")
        if manifest.get("contract", {}).get("version") != "0.3.0":
            errors.append("challenge references a different draft contract version")
        if any(manifest.get(flag) is not False for flag in (
            "contains_renderer_a_output", "contains_target_gold_serialization",
            "contains_verifier_decisions", "contains_fault_labels",
        )):
            errors.append("challenge manifest does not assert no reference-output exposure")
        canonical_content = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        if actual_hash != canonical_sha(canonical_content) or actual_hash != inputs.get("challenge_manifest_sha256"):
            errors.append("challenge manifest self-hash/custodian hash mismatch")
        cases = manifest.get("cases", [])
        if not isinstance(cases, list) or len(cases) != 12:
            errors.append("expected exactly twelve challenge cases")
        else:
            if [c.get("case_id") for c in cases] != [f"RB-{n:03d}" for n in range(1, 13)]:
                errors.append("challenge case IDs/order mismatch")
            if [c.get("scenario_id") for c in cases] != [f"LAB-{n:03d}" for n in range(1, 13)]:
                errors.append("challenge scenario identity mismatch")
            for case in cases:
                case_id = str(case.get("case_id"))
                entry = case.get("input_path")
                expected_path = f"inputs/{case_id}.json"
                if entry != expected_path:
                    errors.append(f"{case_id}: challenge input path not allowlisted")
                    continue
                source = challenge_dir / expected_path
                if not source.is_file():
                    errors.append(f"{case_id}: challenge graph missing")
                    continue
                graph = json.loads(source.read_text(encoding="utf-8"))
                if canonical_sha(graph) != case.get("graph_sha256"):
                    errors.append(f"{case_id}: actual graph hash mismatches manifest")
                check_graph(graph, case_id, errors)

    if not isinstance(declaration, dict):
        errors.append("declaration must be a mapping")
    else:
        identity = declaration.get("independence", {})
        if not isinstance(identity, dict) or identity.get("llm_generated_mapping_code_used") is not True:
            errors.append("Codex mapping authorship must be declared true")
        for flag in (
            "renderer_a_source_inspected_before_initial_commit",
            "renderer_a_outputs_inspected_before_initial_commit",
            "renderer_a_mapping_code_reused",
            "shared_semantic_mapping_utility_used",
        ):
            if identity.get(flag) is not False:
                errors.append(f"clean-room exposure violation: {flag}")
        if identity.get("accidental_exposure"):
            errors.append("accidental exposure disclosed; require quarantine")
        if identity.get("declaration_complete") is not True:
            errors.append("implementation declaration is incomplete")
        if declaration.get("contract") != {"contract_id": "F2V-LAB-ORU-R01-001", "contract_version": "0.3.0"}:
            errors.append("declaration contract identity mismatch")
        if declaration.get("implementation_period", {}).get("completed_on") is None:
            errors.append("implementation completion date missing")
        tokens = ("TO_BE_", "TO-BE-", "2099-")
        for value in (declaration.get("renderer_id"), declaration.get("contributor", {}).get("identity"), declaration.get("implementation", {}).get("language"), declaration.get("implementation_period", {}).get("started_on")):
            if isinstance(value, str) and any(x in value.upper() for x in tokens):
                errors.append("declaration still contains implementer placeholder")
                break

    return {
        "ready_for_exploratory_agent_comparison": not errors,
        "ready_for_differential_comparison": False,
        "scientific_independence_qualified": False,
        "confirmatory_permission": False,
        "blockers": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("declaration", type=Path)
    parser.add_argument("--expected-inputs", required=True, type=Path)
    parser.add_argument("--challenge-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    record = assess(args.declaration, args.expected_inputs, args.challenge_dir)
    rendered = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if record["ready_for_exploratory_agent_comparison"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
