"""Deterministically build the final pre-opening freeze manifest."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.analysis_preregistration import (
    assess_analysis_preregistration,
)
from fhirbridge.artifact_bundle import hash_components_from_manifest
from fhirbridge.expert_assignments import assess_case_assignment_manifest
from fhirbridge.expert_roles import assess_reviewer_roster
from fhirbridge.freeze_audit import assess_presealed_freeze
from fhirbridge.model_config_readiness import assess_model_prompt_freeze
from fhirbridge.pilot_acceptance import (
    assess_pilot_acceptance_preregistration,
)
from fhirbridge.primary_vur_hypothesis import (
    assess_primary_vur_hypothesis,
)
from fhirbridge.sample_size_readiness import assess_sample_size_preregistration
from fhirbridge.sealed_case_manifest import sealed_case_ids
from fhirbridge.tooling_manifest import assess_freeze_readiness

_SCHEMA = Path("expert_validation/schema/freeze_manifest.schema.json")
_DEFAULT_OUTPUT = Path("expert_validation/freeze_manifest.yaml")


def _load(path: Path) -> dict[str, Any]:
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


def _nonzero_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in value)
        or set(value.lower()) == {"0"}
    ):
        raise ValueError(f"{label} is not a frozen SHA-256")
    return value.lower()


def _artifact(
    *,
    artifact_id: str,
    version: str,
    path: Path,
    repository_root: Path,
) -> dict[str, str]:
    try:
        reference = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        reference = str(path)
    return {
        "artifact_id": artifact_id,
        "version": version,
        "path_or_ref": reference,
        "sha256": _sha256(path),
    }


def _case_ids(path: Path) -> set[str]:
    return sealed_case_ids(_load(path))


def _dependencies(tooling: dict[str, Any]) -> list[dict[str, Any]]:
    terminology = tooling["terminology"]
    units = tooling["units"]
    structural = tooling["structural_validation"]
    hl7v2 = structural["hl7v2"]
    fhir = structural["fhir"]

    return [
        {
            "name": "LOINC local snapshot",
            "version": str(terminology["loinc"]["content_version"]),
            "purpose": "terminology",
            "source_or_ref": str(
                terminology["loinc"]["qualification_report"]
            ),
            "sha256": _nonzero_sha256(
                terminology["loinc"]["local_snapshot_sha256"],
                "LOINC local snapshot",
            ),
        },
        {
            "name": "HL7 Terminology package",
            "version": str(terminology["hl7_terminology"]["version"]),
            "purpose": "terminology",
            "source_or_ref": str(
                terminology["hl7_terminology"]["package"]
            ),
            "sha256": _nonzero_sha256(
                terminology["hl7_terminology"]["package_sha256"],
                "HL7 terminology package",
            ),
        },
        {
            "name": "UCUM essence",
            "version": str(units["ucum"]["content_version"]),
            "purpose": "ucum",
            "source_or_ref": str(units["ucum"]["essence_source"]),
            "sha256": _nonzero_sha256(
                units["ucum"]["essence_sha256"],
                "UCUM essence",
            ),
        },
        {
            "name": "FHIR validator CLI",
            "version": str(fhir["validator_cli_version"]),
            "purpose": "fhir_validation",
            "source_or_ref": str(fhir["validator_cli_artifact_source"]),
            "sha256": _nonzero_sha256(
                fhir["validator_cli_artifact_sha256"],
                "FHIR validator CLI",
            ),
        },
        {
            "name": "FHIR package cache manifest",
            "version": "US-Core-9.0.0-resolved-cache",
            "purpose": "fhir_validation",
            "source_or_ref": "qualification/fhir/results/package-cache.sha256",
            "sha256": _nonzero_sha256(
                fhir["package_cache_manifest_sha256"],
                "FHIR package cache manifest",
            ),
        },
        {
            "name": "HL7 v2 validator runtime classpath",
            "version": str(hl7v2["validator_version"]),
            "purpose": "hl7v2_validation",
            "source_or_ref": str(
                hl7v2["validator_runtime_classpath_manifest"]
            ),
            "sha256": _nonzero_sha256(
                hl7v2["validator_runtime_classpath_sha256"],
                "HL7 v2 validator runtime classpath",
            ),
        },
        {
            "name": "LRI Edition 5 machine profile bundle",
            "version": "Edition5-2024DEC",
            "purpose": "hl7v2_validation",
            "source_or_ref": str(hl7v2["profile_artifact"]),
            "sha256": _nonzero_sha256(
                hl7v2["profile_artifact_sha256"],
                "LRI Edition 5 profile bundle",
            ),
        },
    ]


def _role_entries(roster: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for member in roster["members"]:
        for role in member["roles"]:
            result.append(
                {
                    "role_id": member["member_id"],
                    "role": role,
                }
            )
    return result


def _acceptance_summary(pilot: dict[str, Any]) -> str:
    gate = pilot["acceptance_gate"]
    return (
        f"sensitivity {gate['sensitivity_statistic']} >= "
        f"{gate['minimum_sensitivity']}; "
        f"PPV {gate['ppv_statistic']} >= {gate['minimum_ppv']}; "
        f"runtime INDETERMINATE {gate['indeterminate_statistic']} <= "
        f"{gate['maximum_runtime_indeterminate_rate']}"
    )


def build_freeze_manifest(
    *,
    tooling_manifest_path: Path,
    instrument_component_manifest_path: Path,
    reviewer_roster_path: Path,
    case_assignment_path: Path,
    primary_vur_hypothesis_path: Path,
    analysis_preregistration_path: Path,
    sample_size_path: Path,
    model_config_path: Path,
    pilot_acceptance_path: Path,
    sealed_bundle_path: Path,
    sealed_case_manifest_path: Path,
    manifest_id: str,
    freeze_timestamp: str,
    protocol_version: str,
    repository_commit: str,
    bundle_id: str,
    repository_root: Path = Path("."),
    sampling_notes: str | None = None,
    enrichment_or_weighting_plan_ref: str | None = None,
) -> dict[str, Any]:
    tooling = _load(tooling_manifest_path)
    tooling_readiness = assess_freeze_readiness(tooling)
    if not tooling_readiness.ready or tooling_readiness.manifest_status != "frozen":
        raise ValueError("tooling manifest is not confirmatory-frozen")

    roster = _load(reviewer_roster_path)
    roster_readiness = assess_reviewer_roster(roster)
    if not roster_readiness.ready:
        raise ValueError(
            "reviewer roster is not ready: "
            + "; ".join(roster_readiness.blockers)
        )

    sealed_ids = _case_ids(sealed_case_manifest_path)
    assignments = _load(case_assignment_path)
    assignment_readiness = assess_case_assignment_manifest(
        assignments,
        roster,
        expected_case_ids=sealed_ids,
    )
    if not assignment_readiness.ready:
        raise ValueError(
            "case assignment manifest is not ready: "
            + "; ".join(assignment_readiness.blockers)
        )

    primary_hypothesis = _load(primary_vur_hypothesis_path)
    hypothesis_readiness = assess_primary_vur_hypothesis(primary_hypothesis)
    if not hypothesis_readiness.ready:
        raise ValueError(
            "primary hypothesis is not ready: "
            + "; ".join(hypothesis_readiness.blockers)
        )

    analysis = _load(analysis_preregistration_path)
    analysis_readiness = assess_analysis_preregistration(analysis)
    if not analysis_readiness.ready:
        raise ValueError(
            "analysis preregistration is not ready: "
            + "; ".join(analysis_readiness.blockers)
        )

    sample_size = _load(sample_size_path)
    sample_readiness = assess_sample_size_preregistration(sample_size)
    if not sample_readiness.ready:
        raise ValueError(
            "sample-size preregistration is not ready: "
            + "; ".join(sample_readiness.blockers)
        )

    model_config = _load(model_config_path)
    model_readiness = assess_model_prompt_freeze(model_config)
    if not model_readiness.ready:
        raise ValueError(
            "model/prompt configuration is not ready: "
            + "; ".join(model_readiness.blockers)
        )

    pilot = _load(pilot_acceptance_path)
    pilot_readiness = assess_pilot_acceptance_preregistration(pilot)
    if not pilot_readiness.ready:
        raise ValueError(
            "pilot acceptance preregistration is not ready: "
            + "; ".join(pilot_readiness.blockers)
        )

    component_manifest = _load(instrument_component_manifest_path)
    component_digests = hash_components_from_manifest(
        component_manifest,
        repository_root=repository_root,
    )
    component_defs = component_manifest["components"]
    instrument_components = {
        name: {
            "artifact_id": component_defs[name]["artifact_id"],
            "version": f"git:{repository_commit}",
            "path_or_ref": f"component://{name}",
            "sha256": digest.sha256,
        }
        for name, digest in sorted(component_digests.items())
    }

    manifest_version = str(
        component_manifest["instrument_component_manifest"]["version"]
    )
    result = {
        "schema_version": "0.8.0",
        "manifest_id": manifest_id,
        "freeze_timestamp": freeze_timestamp,
        "protocol_version": protocol_version,
        "repository_commit": repository_commit,
        "freeze_complete": True,
        "instrument_component_manifest": _artifact(
            artifact_id="instrument-component-manifest",
            version=manifest_version,
            path=instrument_component_manifest_path,
            repository_root=repository_root,
        ),
        "instrument_components": instrument_components,
        "dependencies": _dependencies(tooling),
        "reviewer_roster": _artifact(
            artifact_id="sealed-expert-reviewer-roster",
            version=str(roster["schema_version"]),
            path=reviewer_roster_path,
            repository_root=repository_root,
        ),
        "case_assignment_manifest": _artifact(
            artifact_id="sealed-expert-case-assignments",
            version=str(assignments["schema_version"]),
            path=case_assignment_path,
            repository_root=repository_root,
        ),
        "primary_vur_hypothesis": _artifact(
            artifact_id="primary-vur-hypothesis-preregistration",
            version=str(primary_hypothesis["schema_version"]),
            path=primary_vur_hypothesis_path,
            repository_root=repository_root,
        ),
        "analysis_preregistration": _artifact(
            artifact_id="confirmatory-analysis-preregistration",
            version=str(analysis["schema_version"]),
            path=analysis_preregistration_path,
            repository_root=repository_root,
        ),
        "sample_size_preregistration": _artifact(
            artifact_id="confirmatory-sample-size-preregistration",
            version=str(sample_size["schema_version"]),
            path=sample_size_path,
            repository_root=repository_root,
        ),
        "model_prompt_configuration": _artifact(
            artifact_id="confirmatory-model-prompt-configuration",
            version=str(model_config["schema_version"]),
            path=model_config_path,
            repository_root=repository_root,
        ),
        "sealed_set": {
            "split": "sealed_test",
            "bundle_id": bundle_id,
            "bundle_sha256": _sha256(sealed_bundle_path),
            "case_count": len(sealed_ids),
            "case_manifest_sha256": _sha256(sealed_case_manifest_path),
            "opened": False,
            "opened_at": None,
            "opened_by_role_ids": [],
            "sampling_notes": sampling_notes,
            "enrichment_or_weighting_plan_ref": enrichment_or_weighting_plan_ref,
        },
        "blinding": {
            "role_ids": _role_entries(roster),
            "model_identity_hidden": True,
            "generation_strategy_hidden": True,
            "verifier_verdict_hidden": True,
            "claimed_provenance_hidden": True,
            "other_reviewer_labels_hidden": True,
            "controls_verified": True,
        },
        "acceptance_gate": {
            "preregistration_ref": str(pilot_acceptance_path),
            "preregistration_sha256": _sha256(pilot_acceptance_path),
            "defined_before_sealed_opening": True,
            "gate_policy_summary": _acceptance_summary(pilot),
        },
        "post_freeze_amendments": [],
    }

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    audit = assess_presealed_freeze(result)
    if not audit.ready_to_open_sealed_set:
        raise ValueError(
            "assembled freeze manifest is not pre-opening ready: "
            + "; ".join(audit.blockers)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tooling-manifest", type=Path, required=True)
    parser.add_argument("--instrument-component-manifest", type=Path, required=True)
    parser.add_argument("--reviewer-roster", type=Path, required=True)
    parser.add_argument("--case-assignments", type=Path, required=True)
    parser.add_argument("--primary-vur-hypothesis", type=Path, required=True)
    parser.add_argument("--analysis-preregistration", type=Path, required=True)
    parser.add_argument("--sample-size", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--pilot-acceptance", type=Path, required=True)
    parser.add_argument("--sealed-bundle", type=Path, required=True)
    parser.add_argument("--sealed-case-manifest", type=Path, required=True)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--freeze-timestamp", required=True)
    parser.add_argument("--protocol-version", required=True)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--sampling-notes")
    parser.add_argument("--enrichment-or-weighting-plan-ref")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_freeze_manifest(
        tooling_manifest_path=args.tooling_manifest,
        instrument_component_manifest_path=args.instrument_component_manifest,
        reviewer_roster_path=args.reviewer_roster,
        case_assignment_path=args.case_assignments,
        primary_vur_hypothesis_path=args.primary_vur_hypothesis,
        analysis_preregistration_path=args.analysis_preregistration,
        sample_size_path=args.sample_size,
        model_config_path=args.model_config,
        pilot_acceptance_path=args.pilot_acceptance,
        sealed_bundle_path=args.sealed_bundle,
        sealed_case_manifest_path=args.sealed_case_manifest,
        manifest_id=args.manifest_id,
        freeze_timestamp=args.freeze_timestamp,
        protocol_version=args.protocol_version,
        repository_commit=args.repository_commit,
        bundle_id=args.bundle_id,
        repository_root=args.repository_root,
        sampling_notes=args.sampling_notes,
        enrichment_or_weighting_plan_ref=args.enrichment_or_weighting_plan_ref,
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
