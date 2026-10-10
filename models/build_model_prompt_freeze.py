"""Deterministically assemble the confirmatory model/prompt freeze."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.artifact_bundle import hash_artifact_bundle
from fhirbridge.baseline_qualification import assess_baseline_qualification
from fhirbridge.model_config_readiness import assess_model_prompt_freeze

_MODEL_SCHEMA = Path("models/schema/model_prompt_freeze.schema.json")
_DECLARATION_SCHEMA = Path("models/schema/model_declarations.schema.json")
_BASELINE_SCHEMA = Path("models/schema/baseline_qualification.schema.json")
_DEFAULT_EXECUTION_POLICY = Path("models/execution_policy.yaml")
_DEFAULT_DIRECT_PROMPT = Path("models/prompts/direct_structured_v0.1.txt")
_DEFAULT_MAPPING_PROMPT = Path("models/prompts/mapping_aware_v0.1.txt")
_DEFAULT_STRATEGY_IMPL = Path("src/fhirbridge/model_strategies.py")
_DEFAULT_SYNTAX_REPAIR = Path("src/fhirbridge/syntax_repair.py")
_DEFAULT_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_DEFAULT_COMPONENT_MANIFEST = Path("benchmark/instrument_component_manifest.yaml")
_DEFAULT_MAPPING_CONTEXT = Path("models/generated/frozen_mapping_context.json")
_DEFAULT_MAPPING_MANIFEST = Path(
    "models/generated/frozen_mapping_context_manifest.json"
)
_DEFAULT_OUTPUT = Path("models/model_prompt_freeze.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path, *, repository_root: Path) -> dict[str, str]:
    try:
        reference = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        reference = str(path)
    return {
        "path_or_ref": reference,
        "sha256": _sha256(path),
    }


def _validate_schema(document: dict[str, Any], schema_path: Path) -> None:
    schema = _load_json(schema_path)
    jsonschema.Draft202012Validator(schema).validate(document)


def _baseline_component_digest(
    component_manifest: dict[str, Any],
    *,
    repository_root: Path,
) -> tuple[str, str]:
    components = component_manifest.get("components")
    if not isinstance(components, dict):
        raise ValueError("instrument component manifest has no components")
    baseline = components.get("deterministic_baseline_renderer")
    if not isinstance(baseline, dict):
        raise ValueError(
            "instrument component manifest lacks deterministic_baseline_renderer"
        )
    artifact_id = baseline.get("artifact_id")
    paths = baseline.get("paths")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ValueError("baseline component artifact_id is missing")
    if not isinstance(paths, list) or not all(
        isinstance(item, str) for item in paths
    ):
        raise ValueError("baseline component paths are malformed")
    digest = hash_artifact_bundle(
        repository_root=repository_root,
        component_id=artifact_id,
        relative_paths=paths,
    )
    return artifact_id, digest.sha256


def _execution_policy_record(
    policy: dict[str, Any],
    *,
    policy_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    metadata = policy.get("execution_policy")
    generation = policy.get("generation_attempt")
    retry = policy.get("retry_policy")
    timeout = policy.get("timeout")
    if not all(
        isinstance(item, dict)
        for item in (metadata, generation, retry, timeout)
    ):
        raise ValueError("execution policy is malformed")
    if metadata.get("status") != "frozen_provider_independent":
        raise ValueError("provider-independent execution policy is not frozen")
    if generation.get("silent_model_fallback") != "prohibited":
        raise ValueError("silent model fallback is not prohibited")
    if generation.get("silent_prompt_fallback") != "prohibited":
        raise ValueError("silent prompt fallback is not prohibited")

    calls = generation.get("provider_generation_calls_per_case_model")
    if not isinstance(calls, dict):
        raise ValueError("provider generation-call policy is missing")
    retry_on = retry.get("retry_on")
    if not isinstance(retry_on, list):
        raise ValueError("retry_on must be a list")

    return {
        "policy_id": metadata.get("id"),
        "policy_version": str(metadata.get("version")),
        "policy_artifact": _artifact(
            policy_path,
            repository_root=repository_root,
        ),
        "synthetic_data_only_for_hosted_models": (
            metadata.get("synthetic_data_only") is True
        ),
        "provider_generation_calls_per_case_model": dict(calls),
        "silent_model_fallback": False,
        "silent_prompt_fallback": False,
        "retry_policy": {
            "maximum_attempts": retry.get("maximum_attempts"),
            "retry_on": list(retry_on),
        },
        "timeout_seconds": timeout.get("seconds"),
    }


def build_model_prompt_freeze(
    *,
    model_declarations_path: Path,
    baseline_qualification_path: Path,
    mapping_context_path: Path,
    mapping_context_manifest_path: Path,
    instrument_component_manifest_path: Path,
    config_id: str,
    created_at: str,
    repository_root: Path = Path("."),
    execution_policy_path: Path = _DEFAULT_EXECUTION_POLICY,
    direct_prompt_path: Path = _DEFAULT_DIRECT_PROMPT,
    mapping_prompt_path: Path = _DEFAULT_MAPPING_PROMPT,
    strategy_implementation_path: Path = _DEFAULT_STRATEGY_IMPL,
    syntax_repair_path: Path = _DEFAULT_SYNTAX_REPAIR,
    contract_path: Path = _DEFAULT_CONTRACT,
) -> dict[str, Any]:
    declarations = _load_yaml(model_declarations_path)
    _validate_schema(declarations, _DECLARATION_SCHEMA)

    baseline_qualification = _load_yaml(baseline_qualification_path)
    _validate_schema(baseline_qualification, _BASELINE_SCHEMA)
    baseline_readiness = assess_baseline_qualification(baseline_qualification)
    if not baseline_readiness.ready:
        raise ValueError(
            "deterministic baseline qualification is not ready: "
            + "; ".join(baseline_readiness.blockers)
        )

    component_manifest = _load_yaml(instrument_component_manifest_path)
    baseline_artifact_id, baseline_digest = _baseline_component_digest(
        component_manifest,
        repository_root=repository_root,
    )
    baseline_record = baseline_qualification["renderer_component"]
    if baseline_record.get("artifact_id") != baseline_artifact_id:
        raise ValueError(
            "baseline qualification artifact_id does not match component manifest"
        )
    if baseline_record.get("sha256") != baseline_digest:
        raise ValueError(
            "baseline qualification renderer digest does not match actual "
            "path-bound component"
        )

    contract_hash = _sha256(contract_path)
    if baseline_qualification["contract"].get("sha256") != contract_hash:
        raise ValueError(
            "baseline qualification contract hash does not match frozen contract"
        )

    mapping_manifest = _load_json(mapping_context_manifest_path)
    mapping_hash = _sha256(mapping_context_path)
    if mapping_manifest.get("sha256") != mapping_hash:
        raise ValueError(
            "frozen mapping-context manifest hash does not match context bytes"
        )

    policy = _load_yaml(execution_policy_path)
    global_policy = _execution_policy_record(
        policy,
        policy_path=execution_policy_path,
        repository_root=repository_root,
    )

    direct_prompt = _artifact(
        direct_prompt_path,
        repository_root=repository_root,
    )
    mapping_prompt = _artifact(
        mapping_prompt_path,
        repository_root=repository_root,
    )
    strategy_impl = _artifact(
        strategy_implementation_path,
        repository_root=repository_root,
    )
    mapping_context = _artifact(
        mapping_context_path,
        repository_root=repository_root,
    )
    syntax_repair = _artifact(
        syntax_repair_path,
        repository_root=repository_root,
    )

    result = {
        "schema_version": "0.6.0",
        "config_id": config_id,
        "status": "frozen",
        "created_at": created_at,
        "sealed_set_opened": False,
        "global_execution_policy": global_policy,
        "deterministic_baseline": {
            "implementation_artifact": {
                "path_or_ref": (
                    "component://deterministic_baseline_renderer"
                ),
                "sha256": baseline_digest,
            },
            "qualification_artifact": _artifact(
                baseline_qualification_path,
                repository_root=repository_root,
            ),
        },
        "llm_models": list(declarations["models"]),
        "llm_strategies": [
            {
                "strategy_id": "direct_structured_llm",
                "generation_source": "provider_call",
                "implementation_artifact": strategy_impl,
                "prompt_artifacts": [direct_prompt],
                "mapping_context_artifacts": [],
                "syntax_repair": {
                    "enabled": False,
                    "implementation_artifact": None,
                },
            },
            {
                "strategy_id": "mapping_aware_llm",
                "generation_source": "provider_call",
                "implementation_artifact": strategy_impl,
                "prompt_artifacts": [mapping_prompt],
                "mapping_context_artifacts": [mapping_context],
                "syntax_repair": {
                    "enabled": False,
                    "implementation_artifact": None,
                },
            },
            {
                "strategy_id": "mapping_aware_plus_syntax_repair",
                "generation_source": "reuse_mapping_aware_raw_output",
                "implementation_artifact": strategy_impl,
                "prompt_artifacts": [mapping_prompt],
                "mapping_context_artifacts": [mapping_context],
                "syntax_repair": {
                    "enabled": True,
                    "implementation_artifact": syntax_repair,
                },
            },
        ],
    }

    _validate_schema(result, _MODEL_SCHEMA)
    readiness = assess_model_prompt_freeze(result)
    if not readiness.ready:
        raise ValueError(
            "assembled model/prompt freeze is not ready: "
            + "; ".join(readiness.blockers)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--baseline-qualification", type=Path, required=True)
    parser.add_argument(
        "--mapping-context",
        type=Path,
        default=_DEFAULT_MAPPING_CONTEXT,
    )
    parser.add_argument(
        "--mapping-context-manifest",
        type=Path,
        default=_DEFAULT_MAPPING_MANIFEST,
    )
    parser.add_argument(
        "--instrument-component-manifest",
        type=Path,
        default=_DEFAULT_COMPONENT_MANIFEST,
    )
    parser.add_argument("--config-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_model_prompt_freeze(
        model_declarations_path=args.models,
        baseline_qualification_path=args.baseline_qualification,
        mapping_context_path=args.mapping_context,
        mapping_context_manifest_path=args.mapping_context_manifest,
        instrument_component_manifest_path=args.instrument_component_manifest,
        config_id=args.config_id,
        created_at=args.created_at,
        repository_root=args.repository_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(result, sort_keys=False),
        encoding="utf-8",
    )
    print(yaml.safe_dump(result, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
