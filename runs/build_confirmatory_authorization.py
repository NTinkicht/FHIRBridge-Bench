"""Build an auditable confirmatory-inference authorization record."""

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

from fhirbridge.artifact_bundle import hash_components_from_manifest
from fhirbridge.confirmatory_authorization import (
    assess_confirmatory_authorization,
)

_SCHEMA = Path("runs/schema/confirmatory_authorization_record.schema.json")
_DEFAULT_OUTPUT = Path("runs/confirmatory_authorization.json")


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


def _load_case_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        value = yaml.safe_load(text)

    if isinstance(value, dict):
        value = value.get("case_ids")
    if not isinstance(value, list) or not value:
        raise ValueError(
            "sealed case ID file must be a non-empty list or {case_ids: [...]}"
        )

    result: set[str] = set()
    for case_id in value:
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("sealed case IDs must be non-empty strings")
        if case_id in result:
            raise ValueError(f"duplicate sealed case ID: {case_id}")
        result.add(case_id)
    return result


def _case_ids_sha256(case_ids: set[str]) -> str:
    payload = json.dumps(
        sorted(case_ids),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def build_authorization_record(
    *,
    protocol_gates_path: Path,
    tooling_manifest_path: Path,
    freeze_manifest_path: Path,
    instrument_component_manifest_path: Path,
    reviewer_roster_path: Path,
    case_assignment_path: Path,
    analysis_preregistration_path: Path,
    sample_size_path: Path,
    model_config_path: Path,
    pilot_acceptance_path: Path,
    sealed_case_ids_path: Path,
    authorization_id: str,
    created_at: str,
    repository_commit: str | None = None,
    repository_root: Path = Path("."),
) -> dict[str, Any]:
    paths = {
        "protocol_freeze_gates": protocol_gates_path,
        "tooling_manifest": tooling_manifest_path,
        "freeze_manifest": freeze_manifest_path,
        "instrument_component_manifest": instrument_component_manifest_path,
        "reviewer_roster": reviewer_roster_path,
        "case_assignment_manifest": case_assignment_path,
        "analysis_preregistration": analysis_preregistration_path,
        "sample_size_preregistration": sample_size_path,
        "model_prompt_configuration": model_config_path,
        "pilot_acceptance_preregistration": pilot_acceptance_path,
    }
    documents = {
        key: _load_document(path)
        for key, path in paths.items()
    }
    artifact_hashes = {
        key: _sha256(path)
        for key, path in paths.items()
    }
    sealed_case_ids = _load_case_ids(sealed_case_ids_path)

    component_digests = hash_components_from_manifest(
        documents["instrument_component_manifest"],
        repository_root=repository_root,
    )
    component_hashes = {
        name: digest.sha256
        for name, digest in sorted(component_digests.items())
    }
    current_commit = _repository_commit(repository_commit)

    decision = assess_confirmatory_authorization(
        protocol_gates=documents["protocol_freeze_gates"],
        tooling_manifest=documents["tooling_manifest"],
        freeze_manifest=documents["freeze_manifest"],
        reviewer_roster=documents["reviewer_roster"],
        case_assignment_manifest=documents["case_assignment_manifest"],
        analysis_preregistration=documents["analysis_preregistration"],
        sample_size_preregistration=documents["sample_size_preregistration"],
        model_prompt_configuration=documents["model_prompt_configuration"],
        pilot_acceptance_preregistration=documents[
            "pilot_acceptance_preregistration"
        ],
        actual_artifact_sha256={
            "instrument_component_manifest": artifact_hashes[
                "instrument_component_manifest"
            ],
            "sealed_case_manifest": _sha256(sealed_case_ids_path),
            "reviewer_roster": artifact_hashes["reviewer_roster"],
            "case_assignment_manifest": artifact_hashes[
                "case_assignment_manifest"
            ],
            "analysis_preregistration": artifact_hashes[
                "analysis_preregistration"
            ],
            "sample_size_preregistration": artifact_hashes[
                "sample_size_preregistration"
            ],
            "model_prompt_configuration": artifact_hashes[
                "model_prompt_configuration"
            ],
            "pilot_acceptance_preregistration": artifact_hashes[
                "pilot_acceptance_preregistration"
            ],
        },
        actual_component_sha256=component_hashes,
        sealed_case_ids=sealed_case_ids,
        actual_repository_commit=current_commit,
    )

    record = {
        "schema_version": "0.2.0",
        "authorization_id": authorization_id,
        "created_at": created_at,
        "repository_commit": current_commit,
        "authorized": decision.authorized,
        "blockers": list(decision.blockers),
        "input_artifacts": {
            **{
                f"{key}_sha256": artifact_hashes[key]
                for key in (
                    "protocol_freeze_gates",
                    "tooling_manifest",
                    "freeze_manifest",
                    "instrument_component_manifest",
                    "reviewer_roster",
                    "case_assignment_manifest",
                    "analysis_preregistration",
                    "sample_size_preregistration",
                    "model_prompt_configuration",
                    "pilot_acceptance_preregistration",
                )
            },
            "sealed_case_manifest_sha256": _sha256(sealed_case_ids_path),
        },
        "instrument_component_sha256": component_hashes,
        "sealed_case_set": {
            "case_count": len(sealed_case_ids),
            "canonical_case_ids_sha256": _case_ids_sha256(sealed_case_ids),
            "manifest_file_sha256": _sha256(sealed_case_ids_path),
        },
    }

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-gates", type=Path, required=True)
    parser.add_argument("--tooling-manifest", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument(
        "--instrument-component-manifest",
        type=Path,
        required=True,
    )
    parser.add_argument("--reviewer-roster", type=Path, required=True)
    parser.add_argument("--case-assignments", type=Path, required=True)
    parser.add_argument("--analysis-preregistration", type=Path, required=True)
    parser.add_argument("--sample-size", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--pilot-acceptance", type=Path, required=True)
    parser.add_argument("--sealed-case-ids", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-commit")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    record = build_authorization_record(
        protocol_gates_path=args.protocol_gates,
        tooling_manifest_path=args.tooling_manifest,
        freeze_manifest_path=args.freeze_manifest,
        instrument_component_manifest_path=args.instrument_component_manifest,
        reviewer_roster_path=args.reviewer_roster,
        case_assignment_path=args.case_assignments,
        analysis_preregistration_path=args.analysis_preregistration,
        sample_size_path=args.sample_size,
        model_config_path=args.model_config,
        pilot_acceptance_path=args.pilot_acceptance,
        sealed_case_ids_path=args.sealed_case_ids,
        authorization_id=args.authorization_id,
        created_at=args.created_at,
        repository_commit=args.repository_commit,
        repository_root=args.repository_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["authorized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
