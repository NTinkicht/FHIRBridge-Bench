"""Score the contract-scorable development fault batch through real HL7 v2 ER7.

This runner adds Renderer A -> ER7 -> independent HL7 v2 lifter to the
development qualification path. It remains supporting evidence only and does
not replace independent Renderer B or blinded expert validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fhirbridge.schema_validation
from fhirbridge.fault_batch import (
    build_development_fault_batch,
    regenerate_fault_batch_case,
)
from fhirbridge.fault_qualification import (
    FaultQualificationCase,
    qualification_report_to_dict,
    qualify_seeded_faults,
)
from fhirbridge.lifters import Hl7V251OruLifter
from fhirbridge.renderers import Hl7V251OruRendererA
from fhirbridge.structural import Hl7V251OruDevelopmentValidator
from fhirbridge.verifier import classify_graph, compile_verification_policy

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"
_CONTRACT_BLOCKED_OPERATORS = {
    "misattribute_result_to_patient",
    "patient_swap_plus_valid_result",
}


def score_serialized_development_batch() -> dict[str, Any]:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    policy = compile_verification_policy(contract)
    batch = build_development_fault_batch(contract)
    renderer = Hl7V251OruRendererA()
    lifter = Hl7V251OruLifter()
    structural_validator = Hl7V251OruDevelopmentValidator()

    qualification_cases: list[FaultQualificationCase] = []
    cases: list[dict[str, Any]] = []
    skipped_contract_blocked: list[str] = []
    pipeline_failure_ids: list[str] = []

    for case in batch.cases:
        operator_name = str(case.manifest["mutation_operator"])
        if operator_name in _CONTRACT_BLOCKED_OPERATORS:
            skipped_contract_blocked.append(case.case_id)
            continue

        source, mutant = regenerate_fault_batch_case(case)
        expected = tuple(case.manifest["expected_classifications"])
        expected_severity = str(case.manifest["expected_severity"])

        try:
            rendered = renderer.render(mutant, contract=contract)
            structural = structural_validator.validate(rendered.artifact)
            lifted = lifter.lift(
                rendered.artifact,
                artifact_id=f"{case.case_id}-serialized-development",
            )
            result = classify_graph(
                source["facts"],
                list(lifted.facts),
                policy=policy,
            )
            observed_classifications = tuple(
                decision.classification for decision in result.decisions
            )
            observed_severities = tuple(
                decision.severity
                for decision in result.decisions
                if decision.severity is not None
            )
            pipeline_error = None
        except Exception as exc:
            structural = None
            observed_classifications = ()
            observed_severities = ()
            pipeline_error = f"{type(exc).__name__}: {exc}"
            pipeline_failure_ids.append(case.case_id)

        qualification_case = FaultQualificationCase(
            case_id=case.case_id,
            expected_classifications=expected,
            expected_severity=expected_severity,
            observed_classifications=observed_classifications,
            observed_severities=observed_severities,
        )
        qualification_cases.append(qualification_case)
        cases.append(
            {
                "case_id": case.case_id,
                "fault_id": case.fault_id,
                "scenario_id": case.scenario_id,
                "seed": case.seed,
                "mutation_operator": operator_name,
                "expected_classifications": list(expected),
                "observed_classifications": list(observed_classifications),
                "detects_all_expected_classes": (
                    qualification_case.detects_all_expected_classes
                ),
                "exact_class_resolution": qualification_case.exact_class_resolution,
                "development_structural_valid": (
                    structural.valid if structural is not None else None
                ),
                "pipeline_error": pipeline_error,
            }
        )

    if not qualification_cases:
        raise ValueError("no serialized development cases were scored")

    report = qualify_seeded_faults(qualification_cases)
    return {
        "purpose": "pre_freeze_serialized_hl7v2_development_fault_scoring",
        "renderer": "Hl7V251OruRendererA",
        "lifter": "Hl7V251OruLifter",
        "structural_gate": "Hl7V251OruDevelopmentValidator",
        "full_profile_validation": False,
        "batch_sha256": batch.batch_sha256,
        "source_batch_case_count": len(batch.cases),
        "scored_case_count": len(qualification_cases),
        "contract_blocked_case_count": len(skipped_contract_blocked),
        "contract_blocked_case_ids": skipped_contract_blocked,
        "pipeline_failure_count": len(pipeline_failure_ids),
        "pipeline_failure_ids": pipeline_failure_ids,
        "report": qualification_report_to_dict(report),
        "cases": cases,
    }


def main() -> int:
    payload = score_serialized_development_batch()
    output_dir = Path("qualification/faults/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "serialized-development-fault-qualification.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "source_batch_case_count": payload["source_batch_case_count"],
        "scored_case_count": payload["scored_case_count"],
        "contract_blocked_case_count": payload["contract_blocked_case_count"],
        "pipeline_failure_count": payload["pipeline_failure_count"],
        "all_expected_classes_detected": payload["report"][
            "all_expected_classes_detected"
        ],
        "exact_class_resolution": payload["report"]["exact_class_resolution"],
        "unresolved_case_count": len(payload["report"]["unresolved_case_ids"]),
        "output": str(output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
