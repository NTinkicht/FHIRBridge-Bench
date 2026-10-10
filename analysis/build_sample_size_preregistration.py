"""Build the pilot-derived sample-size preregistration deterministically."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.sample_size_planning import (
    plan_paired_mcnemar,
    plan_proportion_precision,
)
from fhirbridge.sample_size_readiness import (
    assess_sample_size_preregistration,
)

_INPUT_SCHEMA = Path(
    "analysis/schema/pilot_sample_size_inputs.schema.json"
)
_OUTPUT_SCHEMA = Path(
    "analysis/schema/sample_size_preregistration.schema.json"
)
_CORE_DESIGN = Path("analysis/core_confirmatory_design.yaml")
_METHOD = Path("analysis/sample_size_method.yaml")
_DEFAULT_OUTPUT = Path("analysis/sample_size_preregistration.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _base_comparison_ids(core_design: dict[str, Any]) -> tuple[str, ...]:
    design = core_design.get("analysis_design")
    if not isinstance(design, dict):
        raise ValueError("core design lacks analysis_design")
    family = design.get("paired_secondary_comparison_family")
    if not isinstance(family, dict):
        raise ValueError("core design lacks paired comparison family")
    rows = family.get("base_comparisons")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("core design must define exactly six base comparisons")

    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("base comparison must be a mapping")
        comparison_id = row.get("comparison_id")
        if not isinstance(comparison_id, str) or not comparison_id:
            raise ValueError("base comparison requires comparison_id")
        if comparison_id in result:
            raise ValueError(f"duplicate base comparison: {comparison_id}")
        result.append(comparison_id)
    return tuple(result)


def _planning_constants(method: dict[str, Any]) -> tuple[float, float, float]:
    root = method.get("sample_size_method")
    if not isinstance(root, dict):
        raise ValueError("sample size method lacks sample_size_method")
    paired = root.get("paired_secondary_planning")
    if not isinstance(paired, dict):
        raise ValueError("sample size method lacks paired planning")

    alpha = paired.get("per_comparison_planning_alpha")
    if not isinstance(alpha, (int, float)) or not 0 < float(alpha) < 1:
        raise ValueError("planning alpha is invalid")

    familywise_alpha = paired.get("familywise_alpha")
    if (
        not isinstance(familywise_alpha, (int, float))
        or not 0 < float(familywise_alpha) < 1
    ):
        raise ValueError("familywise alpha is invalid")

    power = paired.get("power")
    if not isinstance(power, (int, float)) or not 0 < float(power) < 1:
        raise ValueError("planning power is invalid")
    return float(alpha), float(familywise_alpha), float(power)


def assemble_sample_size_preregistration(
    *,
    pilot_inputs: dict[str, Any],
    pilot_case_manifest_sha256: str,
    pilot_analysis_sha256: str,
    record_id: str,
    created_at: str,
    core_design: dict[str, Any],
    method: dict[str, Any],
    sample_size_method_sha256: str,
    core_confirmatory_design_sha256: str,
) -> dict[str, Any]:
    """Compute every numeric planning output from frozen pilot-derived inputs."""

    comparison_ids = _base_comparison_ids(core_design)
    alpha, familywise_alpha, power = _planning_constants(method)

    pilot_rows = pilot_inputs.get("paired_comparisons")
    if not isinstance(pilot_rows, list):
        raise ValueError("pilot inputs lack paired_comparisons")
    pilot_by_id: dict[str, dict[str, Any]] = {}
    for row in pilot_rows:
        if not isinstance(row, dict):
            raise ValueError("pilot comparison input must be a mapping")
        comparison_id = row.get("comparison_id")
        if not isinstance(comparison_id, str) or not comparison_id:
            raise ValueError("pilot comparison input lacks comparison_id")
        if comparison_id in pilot_by_id:
            raise ValueError(f"duplicate pilot comparison: {comparison_id}")
        pilot_by_id[comparison_id] = row

    if set(pilot_by_id) != set(comparison_ids):
        raise ValueError(
            "pilot comparison set must match core design exactly; "
            f"missing={sorted(set(comparison_ids) - set(pilot_by_id))}, "
            f"unexpected={sorted(set(pilot_by_id) - set(comparison_ids))}"
        )

    expected_vur = float(pilot_inputs["expected_vur"])
    retention = float(pilot_inputs["valid_determinate_retention"])
    mean_cluster_size = float(pilot_inputs["mean_cluster_size"])
    icc = float(pilot_inputs["icc"])
    target_half_width = float(pilot_inputs["target_half_width"])

    primary = plan_proportion_precision(
        expected_rate=expected_vur,
        target_half_width=target_half_width,
        mean_cluster_size=mean_cluster_size,
        icc=icc,
        expected_analysis_retention=retention,
        confidence_level=0.95,
    )

    pair_plans: list[dict[str, Any]] = []
    required_cluster_counts = [primary.planned_source_cluster_count]
    for comparison_id in comparison_ids:
        source = pilot_by_id[comparison_id]
        plan = plan_paired_mcnemar(
            p10=float(source["p10"]),
            p01=float(source["p01"]),
            mean_cluster_size=mean_cluster_size,
            icc=icc,
            expected_pair_retention=float(source["expected_pair_retention"]),
            alpha=alpha,
            power=power,
        )
        required_cluster_counts.append(plan.planned_source_cluster_count)
        pair_plans.append(
            {
                "comparison_id": comparison_id,
                "p10": plan.p10,
                "p01": plan.p01,
                "alpha": plan.alpha,
                "power": plan.power,
                "expected_pair_retention": plan.expected_pair_retention,
                "independent_pair_row_n": plan.independent_pair_row_n,
                "design_effect": plan.design_effect,
                "cluster_inflated_pair_row_n": (
                    plan.cluster_inflated_pair_row_n
                ),
                "attempted_pair_row_n": plan.attempted_pair_row_n,
                "planned_source_cluster_count": (
                    plan.planned_source_cluster_count
                ),
                "planning_method": plan.method,
            }
        )

    if abs(familywise_alpha - 0.05) > 1e-12:
        raise ValueError("familywise alpha has drifted from 0.05")

    result = {
        "schema_version": "0.4.0",
        "record_id": record_id,
        "status": "preregistered",
        "created_at": created_at,
        "sealed_set_opened": False,
        "frozen_method": {
            "sample_size_method_sha256": sample_size_method_sha256,
            "core_confirmatory_design_sha256": (
                core_confirmatory_design_sha256
            ),
        },
        "pilot_evidence": {
            "pilot_case_manifest_sha256": pilot_case_manifest_sha256,
            "pilot_analysis_sha256": pilot_analysis_sha256,
            "expected_vur": expected_vur,
            "valid_determinate_retention": retention,
            "mean_cluster_size": mean_cluster_size,
            "icc": icc,
        },
        "primary_precision_plan": {
            "confidence_level": primary.confidence_level,
            "target_half_width": primary.target_half_width,
            "independent_row_n": primary.independent_row_n,
            "design_effect": primary.design_effect,
            "cluster_inflated_row_n": primary.cluster_inflated_row_n,
            "attempted_row_n": primary.attempted_row_n,
            "planned_source_cluster_count": (
                primary.planned_source_cluster_count
            ),
        },
        "paired_comparison_plans": pair_plans,
        "final_source_cluster_count": max(required_cluster_counts),
        "selection_rule": (
            "maximum_required_source_cluster_count_across_primary_precision_"
            "and_all_predeclared_paired_comparisons"
        ),
        "attestation": {
            "pilot_only_used_for_planning": True,
            "sealed_results_used_for_planning": False,
            "final_source_cluster_count_recorded_before_confirmatory_inference": (
                True
            ),
        },
    }

    readiness = assess_sample_size_preregistration(result)
    if not readiness.ready:
        raise ValueError(
            "assembled sample-size preregistration is not ready: "
            + "; ".join(readiness.blockers)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the pilot-derived sample-size preregistration before "
            "confirmatory inference."
        )
    )
    parser.add_argument("--pilot-inputs", type=Path, required=True)
    parser.add_argument("--pilot-case-manifest", type=Path, required=True)
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    pilot_inputs = _load_yaml(args.pilot_inputs)
    input_schema = json.loads(_INPUT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(input_schema).validate(pilot_inputs)

    result = assemble_sample_size_preregistration(
        pilot_inputs=pilot_inputs,
        pilot_case_manifest_sha256=_sha256_file(args.pilot_case_manifest),
        pilot_analysis_sha256=_sha256_file(args.pilot_inputs),
        record_id=args.record_id,
        created_at=args.created_at,
        core_design=_load_yaml(_CORE_DESIGN),
        method=_load_yaml(_METHOD),
        sample_size_method_sha256=_sha256_file(_METHOD),
        core_confirmatory_design_sha256=_sha256_file(_CORE_DESIGN),
    )

    output_schema = json.loads(_OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(output_schema).validate(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(result, sort_keys=False),
        encoding="utf-8",
    )
    print(yaml.safe_dump(result, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
