"""Score the deterministic development fault batch with the current verifier.

This is supporting instrument-development evidence only. It does not replace
blinded expert adjudication and does not set confirmatory acceptance thresholds.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import fhirbridge.schema_validation
from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.fault_batch import build_development_fault_batch
from fhirbridge.fault_qualification import (
    FaultQualificationCase,
    qualification_report_to_dict,
    qualify_seeded_faults,
)
from fhirbridge.faults import (
    MutatedGraph,
    corrupt_interpretation,
    corrupt_numeric_value,
    corrupt_observation_code,
    corrupt_patient_identifier,
    corrupt_reference_range,
    corrupt_result_status,
    corrupt_unit_without_conversion,
    fabricate_observation,
    misattribute_result_to_patient,
    omit_required_observation,
    shift_observation_time,
)
from fhirbridge.multi_faults import (
    MultiMutatedGraph,
    omission_plus_fabricated_replacement,
    patient_swap_plus_valid_result,
    value_plus_unit_joint_corruption,
)
from fhirbridge.verifier import LiftedFact, classify_graph, compile_verification_policy

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"

_SINGLE_OPERATORS: dict[str, Callable[[dict[str, Any]], MutatedGraph]] = {
    "fabricate_observation": fabricate_observation,
    "omit_required_observation": omit_required_observation,
    "misattribute_result_to_patient": misattribute_result_to_patient,
    "corrupt_numeric_value": corrupt_numeric_value,
    "corrupt_unit_without_conversion": corrupt_unit_without_conversion,
    "corrupt_observation_code": corrupt_observation_code,
    "corrupt_patient_identifier": corrupt_patient_identifier,
    "shift_observation_time": shift_observation_time,
    "corrupt_result_status": corrupt_result_status,
    "corrupt_interpretation": corrupt_interpretation,
    "corrupt_reference_range": corrupt_reference_range,
}

_MULTI_OPERATORS: dict[str, Callable[[dict[str, Any]], MultiMutatedGraph]] = {
    "value_plus_unit_joint_corruption": value_plus_unit_joint_corruption,
    "patient_swap_plus_valid_result": patient_swap_plus_valid_result,
    "omission_plus_fabricated_replacement": omission_plus_fabricated_replacement,
}


def _lift_graph(graph: dict[str, Any]) -> list[LiftedFact]:
    """Create a representation-local target graph without using verifier logic."""

    facts: list[LiftedFact] = []
    for fact in graph["facts"]:
        payload = deepcopy(fact)
        relationships = tuple(
            (relation["relation_type"], relation["target_fact_id"])
            for relation in fact.get("relations", [])
        )
        lifted_id = f"lifted::{fact['fact_id']}"
        subject_ref = (
            f"lifted::{fact['subject_ref']}"
            if fact.get("subject_ref")
            else None
        )
        payload["subject_ref"] = subject_ref
        payload["relations"] = [
            {
                "relation_type": relation_type,
                "target_fact_id": f"lifted::{target_id}",
            }
            for relation_type, target_id in relationships
        ]
        facts.append(
            LiftedFact(
                lifted_fact_id=lifted_id,
                fact_type=fact["fact_type"],
                subject_ref=subject_ref,
                semantic_payload=payload,
                target_paths=(f"development/{fact['fact_id']}",),
                relationships=tuple(
                    (
                        relation_type,
                        f"lifted::{target_id}",
                    )
                    for relation_type, target_id in relationships
                ),
            )
        )
    return facts


def _regenerate_mutant(case) -> tuple[dict[str, Any], dict[str, Any]]:
    source = generate_lab_scenario(case.scenario_id, case.seed)
    operator_name = case.manifest["mutation_operator"]
    if operator_name in _SINGLE_OPERATORS:
        mutated = _SINGLE_OPERATORS[operator_name](source)
        return source, mutated.graph
    if operator_name in _MULTI_OPERATORS:
        mutated = _MULTI_OPERATORS[operator_name](source)
        return source, mutated.graph
    raise ValueError(f"unsupported fault-batch operator: {operator_name}")


def score_development_batch() -> dict[str, Any]:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    policy = compile_verification_policy(contract)
    batch = build_development_fault_batch(contract)

    qualification_cases: list[FaultQualificationCase] = []
    scorable_cases: list[FaultQualificationCase] = []
    per_case: list[dict[str, Any]] = []
    contract_blocked_case_ids: list[str] = []

    for case in batch.cases:
        source, mutant = _regenerate_mutant(case)
        result = classify_graph(
            source["facts"],
            _lift_graph(mutant),
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
        expected = tuple(case.manifest["expected_classifications"])
        expected_severity = str(case.manifest["expected_severity"])
        qualification_case = FaultQualificationCase(
            case_id=case.case_id,
            expected_classifications=expected,
            expected_severity=expected_severity,
            observed_classifications=observed_classifications,
            observed_severities=observed_severities,
        )
        qualification_cases.append(qualification_case)
        contract_blocked = (
            "MISATTRIBUTION" in expected
            and not qualification_case.detects_all_expected_classes
            and any(
                decision.classification == "INDETERMINATE"
                and (
                    decision.evidence.get("rationale_code")
                    == "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
                    or decision.evidence.get("scope_note")
                    == "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
                )
                for decision in result.decisions
            )
        )
        if contract_blocked:
            contract_blocked_case_ids.append(case.case_id)
        else:
            scorable_cases.append(qualification_case)

        per_case.append(
            {
                "case_id": case.case_id,
                "fault_id": case.fault_id,
                "semantic_class": case.semantic_class,
                "scenario_id": case.scenario_id,
                "seed": case.seed,
                "expected_classifications": list(expected),
                "expected_severity": expected_severity,
                "observed_classifications": list(observed_classifications),
                "observed_severities": list(observed_severities),
                "primary_endpoint_verdict": result.primary_endpoint_verdict,
                "detects_all_expected_classes": (
                    qualification_case.detects_all_expected_classes
                ),
                "exact_class_resolution": qualification_case.exact_class_resolution,
                "contract_blocked": contract_blocked,
                "contract_block_reason": (
                    "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
                    if contract_blocked
                    else None
                ),
            }
        )

    all_stimuli_report = qualify_seeded_faults(qualification_cases)
    if not scorable_cases:
        raise ValueError("development batch contains no contract-scorable fault cases")
    scorable_report = qualify_seeded_faults(scorable_cases)
    return {
        "purpose": "pre_freeze_development_seeded_fault_scoring",
        "batch_sha256": batch.batch_sha256,
        "case_count": len(batch.cases),
        "scorable_case_count": len(scorable_cases),
        "contract_blocked_case_count": len(contract_blocked_case_ids),
        "contract_blocked_case_ids": contract_blocked_case_ids,
        "contract_block_reason": "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE",
        "all_stimuli_report": qualification_report_to_dict(all_stimuli_report),
        "scorable_report": qualification_report_to_dict(scorable_report),
        "cases": per_case,
    }


def main() -> int:
    payload = score_development_batch()
    output_dir = Path("qualification/faults/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "development-fault-qualification.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "case_count": payload["case_count"],
        "scorable_case_count": payload["scorable_case_count"],
        "contract_blocked_case_count": payload["contract_blocked_case_count"],
        "batch_sha256": payload["batch_sha256"],
        "scorable_all_expected_classes_detected": payload["scorable_report"][
            "all_expected_classes_detected"
        ],
        "scorable_exact_class_resolution": payload["scorable_report"][
            "exact_class_resolution"
        ],
        "all_stimuli_unresolved_case_count": len(
            payload["all_stimuli_report"]["unresolved_case_ids"]
        ),
        "output": str(output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
