"""Assemble the final confirmatory analysis preregistration fail-closed."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.analysis_preregistration import (
    assess_analysis_preregistration,
)
from fhirbridge.model_config_readiness import assess_model_prompt_freeze
from fhirbridge.primary_vur_hypothesis import (
    assess_primary_vur_hypothesis,
)
from fhirbridge.sample_size_readiness import (
    assess_sample_size_preregistration,
)

_CORE_DESIGN = Path("analysis/core_confirmatory_design.yaml")
_SCHEMA = Path("analysis/schema/analysis_preregistration.schema.json")
_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_STRUCTURAL_POLICY = Path("benchmark/structural_validity_policy.yaml")
_SAP = Path("docs/statistical_analysis_plan.md")
_DEFAULT_OUTPUT = Path("analysis/analysis_preregistration.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
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
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError("repository commit must be a 7-40 character hex SHA")
    return value.lower()


def _base_comparisons(core_design: dict[str, Any]) -> list[dict[str, str]]:
    design = core_design.get("analysis_design")
    if not isinstance(design, dict):
        raise ValueError("core design lacks analysis_design")
    paired = design.get("paired_secondary_comparison_family")
    if not isinstance(paired, dict):
        raise ValueError("core design lacks paired comparison family")
    values = paired.get("base_comparisons")
    if not isinstance(values, list) or len(values) != 6:
        raise ValueError("core design must define exactly six base comparisons")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("base comparison must be a mapping")
        comparison_id = item.get("comparison_id")
        arm_a = item.get("arm_a")
        arm_b = item.get("arm_b")
        if not all(
            isinstance(value, str) and value
            for value in (comparison_id, arm_a, arm_b)
        ):
            raise ValueError("base comparison fields must be non-empty strings")
        if comparison_id in seen:
            raise ValueError(f"duplicate base comparison: {comparison_id}")
        seen.add(comparison_id)
        result.append(
            {
                "comparison_id": comparison_id,
                "arm_a": arm_a,
                "arm_b": arm_b,
            }
        )
    return result


def _model_keys(model_config: dict[str, Any]) -> list[str]:
    models = model_config.get("llm_models")
    if not isinstance(models, list) or not models:
        raise ValueError("frozen model configuration has no LLM models")
    result: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            raise ValueError("LLM model entry is malformed")
        model_key = item.get("model_key")
        if not isinstance(model_key, str) or not model_key:
            raise ValueError("LLM model entry lacks model_key")
        if model_key in result:
            raise ValueError(f"duplicate model_key: {model_key}")
        result.append(model_key)
    return result


def expand_comparison_family(
    model_keys: list[str],
    base_comparisons: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Expand six frozen base contrasts for every frozen model family."""

    if not model_keys:
        raise ValueError("model_keys must not be empty")
    if len(base_comparisons) != 6:
        raise ValueError("exactly six base comparisons are required")
    family: list[dict[str, str]] = []
    for model_key in model_keys:
        for comparison in base_comparisons:
            family.append(
                {
                    "comparison_id": (
                        f"{model_key}__{comparison['comparison_id']}"
                    ),
                    "model_key": model_key,
                    "arm_a": comparison["arm_a"],
                    "arm_b": comparison["arm_b"],
                }
            )
    return family


def assemble_analysis_preregistration(
    *,
    model_config: dict[str, Any],
    sample_size: dict[str, Any],
    primary_hypothesis: dict[str, Any],
    core_design: dict[str, Any],
    repository_commit: str,
    analysis_id: str,
    created_at: str,
    input_hashes: dict[str, str],
) -> dict[str, Any]:
    model_readiness = assess_model_prompt_freeze(model_config)
    if not model_readiness.ready:
        raise ValueError(
            "model/prompt configuration is not freeze-ready: "
            + "; ".join(model_readiness.blockers)
        )
    sample_readiness = assess_sample_size_preregistration(sample_size)
    if not sample_readiness.ready:
        raise ValueError(
            "sample-size preregistration is not freeze-ready: "
            + "; ".join(sample_readiness.blockers)
        )

    hypothesis_readiness = assess_primary_vur_hypothesis(
        primary_hypothesis
    )
    if not hypothesis_readiness.ready:
        raise ValueError(
            "primary VUR hypothesis is not freeze-ready: "
            + "; ".join(hypothesis_readiness.blockers)
        )

    design = core_design.get("analysis_design")
    if not isinstance(design, dict):
        raise ValueError("core design lacks analysis_design")
    paired_analysis = design.get("paired_analysis")
    if not isinstance(paired_analysis, dict):
        raise ValueError("core design lacks paired_analysis")

    keys = _model_keys(model_config)
    base = _base_comparisons(core_design)
    family = expand_comparison_family(keys, base)

    primary = design.get("primary_estimand")
    companion = design.get("companion_estimand")
    if not isinstance(primary, dict) or primary.get("name") != "VUR":
        raise ValueError("core design primary estimand is not VUR")
    if not isinstance(companion, dict) or companion.get("name") != "VFY":
        raise ValueError("core design companion estimand is not VFY")

    required_hashes = {
        "projectability_contract_sha256",
        "structural_validity_policy_sha256",
        "statistical_analysis_plan_sha256",
        "model_prompt_configuration_sha256",
        "sample_size_preregistration_sha256",
        "primary_vur_hypothesis_sha256",
    }
    if set(input_hashes) != required_hashes:
        raise ValueError("input_hashes do not match required frozen inputs")
    for name, digest in input_hashes.items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in digest)
        ):
            raise ValueError(f"{name} is not a SHA-256 digest")

    sample_model_keys = sample_size.get("model_keys")
    if sample_model_keys != keys:
        raise ValueError(
            "sample-size model_keys do not match frozen model configuration"
        )
    frozen_method = sample_size.get("frozen_method")
    if not isinstance(frozen_method, dict):
        raise ValueError("sample-size record lacks frozen_method provenance")
    sample_model_hash = frozen_method.get(
        "model_prompt_configuration_sha256"
    )
    expected_model_hash = input_hashes["model_prompt_configuration_sha256"]
    if (
        not isinstance(sample_model_hash, str)
        or sample_model_hash.lower() != expected_model_hash.lower()
    ):
        raise ValueError(
            "sample-size record was not built from the same frozen model "
            "configuration"
        )

    result = {
        "schema_version": "0.5.0",
        "analysis_id": analysis_id,
        "status": "preregistered",
        "created_at": created_at,
        "sealed_set_opened": False,
        "frozen_inputs": {
            "repository_commit": repository_commit,
            **{
                key: value.lower()
                for key, value in input_hashes.items()
            },
        },
        "primary_estimand": {
            "name": "VUR",
            "direction": design["primary_direction"],
            "structural_condition": "VALID",
            "semantic_condition": "determinate_FAITHFUL_or_UNFAITHFUL",
        },
        "primary_hypothesis": {
            "record_id": primary_hypothesis["record_id"],
            "nontrivial_vur_threshold": primary_hypothesis[
                "hypothesis"
            ]["nontrivial_vur_threshold"],
            "model_strategy_aggregation_policy": primary_hypothesis[
                "target_population"
            ]["model_strategy_aggregation_policy"],
            "inference_method": primary_hypothesis["inference"]["method"],
            "alpha": primary_hypothesis["inference"]["alpha"],
            "sidedness": primary_hypothesis["inference"]["sidedness"],
            "cluster_id_field": primary_hypothesis[
                "target_population"
            ]["cluster_id_field"],
            "decision_rule": primary_hypothesis["inference"][
                "decision_rule"
            ],
        },
        "paired_comparisons": {
            "analysis_set_rule": paired_analysis["VUR_analysis_set_rule"],
            "cluster_id_field": paired_analysis["cluster_id_field"],
            "model_keys": keys,
            "comparison_family": family,
        },
        "multiplicity": {
            "secondary_pairwise_method": "Holm",
            "comparison_family_size": len(family),
        },
        "bootstrap": deepcopy(paired_analysis["bootstrap"]),
        "mcnemar": deepcopy(paired_analysis["mcnemar"]),
        "companion_estimand": deepcopy(companion),
    }

    readiness = assess_analysis_preregistration(result)
    if not readiness.ready:
        raise ValueError(
            "assembled analysis preregistration is not ready: "
            + "; ".join(readiness.blockers)
        )
    return result


def build_from_paths(
    *,
    model_config_path: Path,
    sample_size_path: Path,
    primary_hypothesis_path: Path,
    analysis_id: str,
    created_at: str,
    repository_commit: str | None = None,
) -> dict[str, Any]:
    model_config = _load_yaml(model_config_path)
    sample_size = _load_yaml(sample_size_path)
    primary_hypothesis = _load_yaml(primary_hypothesis_path)
    core_design = _load_yaml(_CORE_DESIGN)
    result = assemble_analysis_preregistration(
        model_config=model_config,
        sample_size=sample_size,
        primary_hypothesis=primary_hypothesis,
        core_design=core_design,
        repository_commit=_repository_commit(repository_commit),
        analysis_id=analysis_id,
        created_at=created_at,
        input_hashes={
            "projectability_contract_sha256": _sha256(_CONTRACT),
            "structural_validity_policy_sha256": _sha256(_STRUCTURAL_POLICY),
            "statistical_analysis_plan_sha256": _sha256(_SAP),
            "model_prompt_configuration_sha256": _sha256(model_config_path),
            "sample_size_preregistration_sha256": _sha256(sample_size_path),
            "primary_vur_hypothesis_sha256": _sha256(
                primary_hypothesis_path
            ),
        },
    )

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--sample-size", type=Path, required=True)
    parser.add_argument("--primary-hypothesis", type=Path, required=True)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-commit")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_from_paths(
        model_config_path=args.model_config,
        sample_size_path=args.sample_size,
        primary_hypothesis_path=args.primary_hypothesis,
        analysis_id=args.analysis_id,
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
