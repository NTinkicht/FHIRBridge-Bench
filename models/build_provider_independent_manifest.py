"""Hash provider-independent model-strategy artifacts for audit evidence."""

from __future__ import annotations

import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path

_OUTPUT = Path("models/generated/provider_independent_artifact_manifest.json")
_ARTIFACTS = (
    Path("models/execution_policy.yaml"),
    Path("models/prompts/direct_structured_v0.1.txt"),
    Path("models/prompts/mapping_aware_v0.1.txt"),
    Path("src/fhirbridge/model_strategies.py"),
    Path("src/fhirbridge/syntax_repair.py"),
    Path("src/fhirbridge/mapping_context.py"),
    Path("models/build_frozen_mapping_context.py"),
    Path("models/schema/model_execution_record.schema.json"),
    Path("src/fhirbridge/model_execution.py"),
    Path("runs/validate_execution_records.py"),
    Path("src/fhirbridge/confirmatory_authorization.py"),
    Path("runs/schema/confirmatory_authorization_record.schema.json"),
    Path("runs/build_confirmatory_authorization.py"),
    Path("runs/build_confirmatory_run_plan.py"),
    Path("analysis/build_analysis_preregistration.py"),
    Path("src/fhirbridge/analysis_design_consistency.py"),
    Path("benchmark/severity_policy_candidate.yaml"),
    Path("expert_validation/severity_anchor_set.yaml"),
    Path("expert_validation/schema/severity_blind_response.schema.json"),
    Path("expert_validation/build_severity_blind_packet.py"),
    Path("src/fhirbridge/severity_blind_review.py"),
    Path("expert_validation/score_severity_blind_pair.py"),
    Path("benchmark/error_precedence_policy_candidate.yaml"),
    Path("expert_validation/schema/precedence_blind_response.schema.json"),
    Path("expert_validation/build_precedence_blind_packet.py"),
    Path("src/fhirbridge/precedence_blind_review.py"),
    Path("expert_validation/score_precedence_blind_pair.py"),
    Path("expert_validation/schema/severity_calibration.schema.json"),
    Path("src/fhirbridge/severity_calibration.py"),
    Path("expert_validation/finalize_severity_policy.py"),
    Path("expert_validation/schema/precedence_review.schema.json"),
    Path("src/fhirbridge/precedence_review.py"),
    Path("expert_validation/finalize_precedence_policy.py"),
    Path("src/fhirbridge/measurement_policy_readiness.py"),
    Path("runs/schema/confirmatory_run_plan.schema.json"),
    Path("src/fhirbridge/confirmatory_run_plan.py"),
    Path("src/fhirbridge/confirmatory_execution_audit.py"),
    Path("runs/schema/confirmatory_result_manifest.schema.json"),
    Path("src/fhirbridge/confirmatory_result_manifest.py"),
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _repository_commit() -> str:
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_manifest() -> dict[str, object]:
    missing = [str(path) for path in _ARTIFACTS if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing strategy artifacts: " + ", ".join(missing))

    return {
        "manifest_id": "FHIRBRIDGE-PROVIDER-INDEPENDENT-ARTIFACTS-001",
        "status": "prefreeze_provider_independent",
        "repository_commit": _repository_commit(),
        "artifacts": [
            {
                "path": str(path),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in _ARTIFACTS
        ],
        "scientific_scope": [
            "prompt_templates",
            "execution_policy",
            "strategy_assembly",
            "syntax_repair",
            "mapping_context_generation_code",
            "confirmatory_run_authorization",
            "authorization_record_assembly",
            "confirmatory_run_plan_assembly",
            "analysis_preregistration_assembly",
            "cross_file_analysis_design_consistency",
            "measurement_error_policy_candidates",
            "severity_blind_calibration_handoff",
            "severity_calibration_and_finalization",
            "precedence_independent_review_handoff",
            "precedence_review_and_finalization",
            "pre_inference_run_plan",
            "execution_record_schema_validation",
            "post_run_execution_completeness_audit",
            "post_run_result_provenance_manifest",
        ],
        "not_included": [
            "final_model_provider_snapshot",
            "final_frozen_mapping_context",
            "deterministic_baseline_order_projection",
        ],
    }


def main() -> int:
    manifest = build_manifest()
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
