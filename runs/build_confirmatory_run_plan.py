"""Assemble a confirmatory run plan only from already-authorized frozen inputs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.confirmatory_run_plan import assess_confirmatory_run_plan
from fhirbridge.model_config_readiness import assess_model_prompt_freeze
from fhirbridge.sealed_case_manifest import (
    sealed_case_ids as sealed_case_ids_from_manifest,
)

_AUTH_SCHEMA = Path(
    "runs/schema/confirmatory_authorization_record.schema.json"
)
_RUN_PLAN_SCHEMA = Path("runs/schema/confirmatory_run_plan.schema.json")
_EXECUTION_SCHEMA = Path("models/schema/model_execution_record.schema.json")
_DEFAULT_OUTPUT = Path("runs/confirmatory_run_plan.yaml")


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object/mapping")
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _repository_commit(explicit: str | None) -> str:
    if explicit:
        value = explicit
    elif os.environ.get("GITHUB_SHA"):
        value = str(os.environ["GITHUB_SHA"])
    else:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
    if (
        len(value) < 7
        or len(value) > 40
        or any(ch not in "0123456789abcdefABCDEF" for ch in value)
    ):
        raise ValueError("repository commit must be a 7-40 character hex SHA")
    return value.lower()


def _case_ids_sha256(case_ids: set[str]) -> str:
    payload = json.dumps(
        sorted(case_ids),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def build_run_plan(
    *,
    authorization_record_path: Path,
    freeze_manifest_path: Path,
    protocol_gates_path: Path,
    tooling_manifest_path: Path,
    model_config_path: Path,
    analysis_preregistration_path: Path,
    sample_size_path: Path,
    pilot_acceptance_path: Path,
    sealed_bundle_path: Path,
    sealed_case_manifest_path: Path,
    sealed_bundle_id: str,
    run_plan_id: str,
    created_at: str,
    repository_commit: str | None = None,
) -> dict[str, Any]:
    auth = _load_document(authorization_record_path)
    auth_schema = json.loads(_AUTH_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(auth_schema).validate(auth)
    if auth.get("authorized") is not True or auth.get("blockers") != []:
        raise ValueError("authorization record does not authorize inference")

    current_commit = _repository_commit(repository_commit)
    if auth.get("repository_commit") != current_commit:
        raise ValueError(
            "authorization repository_commit does not match current run commit"
        )

    artifact_paths = {
        "protocol_freeze_gates": protocol_gates_path,
        "tooling_manifest": tooling_manifest_path,
        "freeze_manifest": freeze_manifest_path,
        "model_prompt_configuration": model_config_path,
        "analysis_preregistration": analysis_preregistration_path,
        "sample_size_preregistration": sample_size_path,
        "pilot_acceptance_preregistration": pilot_acceptance_path,
    }
    auth_hashes = auth.get("input_artifacts")
    if not isinstance(auth_hashes, dict):
        raise ValueError("authorization record lacks input_artifacts")
    for key, path in artifact_paths.items():
        expected = auth_hashes.get(f"{key}_sha256")
        actual = _sha256(path)
        if expected != actual:
            raise ValueError(
                f"authorized artifact changed after authorization: {key}"
            )

    sealed_case_manifest_sha256 = _sha256(sealed_case_manifest_path)
    if auth_hashes.get("sealed_case_manifest_sha256") != (
        sealed_case_manifest_sha256
    ):
        raise ValueError(
            "authorized sealed case manifest changed after authorization"
        )

    freeze_manifest = _load_document(freeze_manifest_path)
    frozen_sealed = freeze_manifest.get("sealed_set")
    if not isinstance(frozen_sealed, dict):
        raise ValueError("freeze manifest lacks sealed_set binding")

    sealed_bundle_sha256 = _sha256(sealed_bundle_path)
    if frozen_sealed.get("bundle_id") != sealed_bundle_id:
        raise ValueError("sealed bundle ID does not match freeze manifest")
    if frozen_sealed.get("bundle_sha256") != sealed_bundle_sha256:
        raise ValueError("sealed bundle bytes do not match freeze manifest")
    if frozen_sealed.get("case_manifest_sha256") != (
        sealed_case_manifest_sha256
    ):
        raise ValueError(
            "sealed case manifest bytes do not match freeze manifest"
        )

    model_config = _load_document(model_config_path)
    model_readiness = assess_model_prompt_freeze(model_config)
    if not model_readiness.ready:
        raise ValueError(
            "model/prompt configuration is not freeze-ready: "
            + "; ".join(model_readiness.blockers)
        )
    models = model_config.get("llm_models")
    assert isinstance(models, list)
    model_keys = [str(item["model_key"]) for item in models]

    sealed_case_manifest = _load_document(sealed_case_manifest_path)
    case_ids = sealed_case_ids_from_manifest(sealed_case_manifest)
    sealed_case_set = auth.get("sealed_case_set")
    if not isinstance(sealed_case_set, dict):
        raise ValueError("authorization record lacks sealed_case_set")
    if sealed_case_set.get("case_count") != len(case_ids):
        raise ValueError("authorized sealed case count changed")
    if sealed_case_set.get("canonical_case_ids_sha256") != _case_ids_sha256(
        case_ids
    ):
        raise ValueError("authorized sealed case identity set changed")
    if sealed_case_set.get("manifest_file_sha256") != (
        sealed_case_manifest_sha256
    ):
        raise ValueError(
            "authorization sealed case-manifest file hash changed"
        )

    case_count = len(case_ids)
    if frozen_sealed.get("case_count") != case_count:
        raise ValueError("sealed case count does not match freeze manifest")
    model_count = len(model_keys)
    result = {
        "schema_version": "0.3.0",
        "run_plan_id": run_plan_id,
        "status": "prepared_authorized",
        "created_at": created_at,
        "repository_commit": current_commit,
        "sealed_set_opened": False,
        "inference_started": False,
        "authorization": {
            "authorized": True,
            "record_sha256": _sha256(authorization_record_path),
            "record_schema_version": "0.2.0",
            "record_schema_sha256": _sha256(_AUTH_SCHEMA),
        },
        "frozen_artifacts": {
            "freeze_manifest_sha256": _sha256(freeze_manifest_path),
            "protocol_freeze_gates_sha256": _sha256(protocol_gates_path),
            "tooling_manifest_sha256": _sha256(tooling_manifest_path),
            "model_prompt_configuration_sha256": _sha256(model_config_path),
            "analysis_preregistration_sha256": _sha256(
                analysis_preregistration_path
            ),
            "sample_size_preregistration_sha256": _sha256(sample_size_path),
            "pilot_acceptance_preregistration_sha256": _sha256(
                pilot_acceptance_path
            ),
            "execution_record_schema_sha256": _sha256(_EXECUTION_SCHEMA),
        },
        "execution_record_contract": {
            "schema_version": "0.3.0",
            "required_bindings": [
                "model_prompt_freeze_sha256",
                "source_input_sha256",
                "rendered_prompt_sha256",
                "mapping_context_sha256",
            ],
            "mapping_repair_lineage_required": True,
            "schema_validation_required": True,
        },
        "sealed_set": {
            "bundle_id": sealed_bundle_id,
            "bundle_sha256": sealed_bundle_sha256,
            "case_manifest_sha256": sealed_case_manifest_sha256,
            "case_count": case_count,
        },
        "model_keys": model_keys,
        "expected_execution_counts": {
            "provider_generation_calls": case_count * model_count * 2,
            "derived_repair_outputs": case_count * model_count,
            "deterministic_baseline_outputs": case_count,
            "total_arm_outputs": case_count * (1 + 3 * model_count),
        },
    }

    schema = json.loads(_RUN_PLAN_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    readiness = assess_confirmatory_run_plan(result)
    if not readiness.ready:
        raise ValueError(
            "assembled confirmatory run plan is not ready: "
            + "; ".join(readiness.blockers)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-record", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--protocol-gates", type=Path, required=True)
    parser.add_argument("--tooling-manifest", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--analysis-preregistration", type=Path, required=True)
    parser.add_argument("--sample-size", type=Path, required=True)
    parser.add_argument("--pilot-acceptance", type=Path, required=True)
    parser.add_argument("--sealed-bundle", type=Path, required=True)
    parser.add_argument("--sealed-case-manifest", type=Path, required=True)
    parser.add_argument("--sealed-bundle-id", required=True)
    parser.add_argument("--run-plan-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-commit")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_run_plan(
        authorization_record_path=args.authorization_record,
        freeze_manifest_path=args.freeze_manifest,
        protocol_gates_path=args.protocol_gates,
        tooling_manifest_path=args.tooling_manifest,
        model_config_path=args.model_config,
        analysis_preregistration_path=args.analysis_preregistration,
        sample_size_path=args.sample_size,
        pilot_acceptance_path=args.pilot_acceptance,
        sealed_bundle_path=args.sealed_bundle,
        sealed_case_manifest_path=args.sealed_case_manifest,
        sealed_bundle_id=args.sealed_bundle_id,
        run_plan_id=args.run_plan_id,
        created_at=args.created_at,
        repository_commit=args.repository_commit,
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
