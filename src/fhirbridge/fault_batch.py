"""Deterministic development batches for seeded semantic-fault qualification.

The batch generator is deliberately independent of verifier decision logic. It
constructs reproducible stimuli and manifests only; scoring is a separate step.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from .canonical import generate_lab_scenario
from .fault_manifest import manifest_for_multi_fault, manifest_for_seeded_fault
from .faults import (
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
from .multi_faults import (
    MultiMutatedGraph,
    omission_plus_fabricated_replacement,
    patient_swap_plus_valid_result,
    value_plus_unit_joint_corruption,
)


@dataclass(frozen=True)
class FaultBatchCase:
    case_id: str
    semantic_class: str
    scenario_id: str
    seed: int
    fault_id: str
    graph_sha256: str
    manifest: dict[str, Any]


@dataclass(frozen=True)
class FaultBatch:
    schema_version: str
    purpose: str
    cases: tuple[FaultBatchCase, ...]
    batch_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "purpose": self.purpose,
            "case_count": len(self.cases),
            "class_counts": class_counts(self),
            "cases": [asdict(case) for case in self.cases],
            "batch_sha256": self.batch_sha256,
        }


def _json_sha256(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _batch_digest(cases: list[FaultBatchCase]) -> str:
    payload = [
        {
            "case_id": case.case_id,
            "semantic_class": case.semantic_class,
            "scenario_id": case.scenario_id,
            "seed": case.seed,
            "fault_id": case.fault_id,
            "graph_sha256": case.graph_sha256,
            "manifest_sha256": case.manifest["manifest_sha256"],
        }
        for case in cases
    ]
    return _json_sha256({"cases": payload})


def _single_case(
    *,
    case_index: int,
    semantic_class: str,
    scenario_id: str,
    seed: int,
    operator_name: str,
    operator: Callable[[dict[str, Any]], MutatedGraph],
    contract: dict[str, Any],
) -> FaultBatchCase:
    source = generate_lab_scenario(scenario_id, seed)
    mutated = operator(source)
    manifest = manifest_for_seeded_fault(
        source,
        mutated.fault,
        contract=contract,
        mutation_operator=operator_name,
    ).to_dict()
    return FaultBatchCase(
        case_id=f"SF-{case_index:04d}",
        semantic_class=semantic_class,
        scenario_id=scenario_id,
        seed=seed,
        fault_id=mutated.fault.fault_id,
        graph_sha256=_json_sha256(mutated.graph),
        manifest=manifest,
    )


def _multi_case(
    *,
    case_index: int,
    scenario_id: str,
    seed: int,
    operator_name: str,
    operator: Callable[[dict[str, Any]], MultiMutatedGraph],
    contract: dict[str, Any],
) -> FaultBatchCase:
    source = generate_lab_scenario(scenario_id, seed)
    mutated = operator(source)
    manifest = manifest_for_multi_fault(
        source,
        mutated.fault,
        contract=contract,
        mutation_operator=operator_name,
    ).to_dict()
    return FaultBatchCase(
        case_id=f"MF-{case_index:04d}",
        semantic_class="MULTI_FAULT",
        scenario_id=scenario_id,
        seed=seed,
        fault_id=mutated.fault.fault_id,
        graph_sha256=_json_sha256(mutated.graph),
        manifest=manifest,
    )


def build_development_fault_batch(
    contract: dict[str, Any],
    *,
    seed_base: int = 12000,
) -> FaultBatch:
    """Build a deterministic pre-freeze development qualification batch.

    Counts intentionally exceed the planning minimum of 50 single-fault cases
    for each primary semantic class and 100 multi-fault cases. These are
    development stimuli only and cannot substitute for independently authored
    or blinded confirmatory faults.
    """

    cases: list[FaultBatchCase] = []
    index = 1
    seed = seed_base

    # FABRICATION: 50
    for _ in range(50):
        cases.append(
            _single_case(
                case_index=index,
                semantic_class="FABRICATION",
                scenario_id="LAB-001",
                seed=seed,
                operator_name="fabricate_observation",
                operator=fabricate_observation,
                contract=contract,
            )
        )
        index += 1
        seed += 1

    # OMISSION: 50
    for _ in range(50):
        cases.append(
            _single_case(
                case_index=index,
                semantic_class="OMISSION",
                scenario_id="LAB-001",
                seed=seed,
                operator_name="omit_required_observation",
                operator=omit_required_observation,
                contract=contract,
            )
        )
        index += 1
        seed += 1

    # MISATTRIBUTION: 50
    for _ in range(50):
        cases.append(
            _single_case(
                case_index=index,
                semantic_class="MISATTRIBUTION",
                scenario_id="LAB-001",
                seed=seed,
                operator_name="misattribute_result_to_patient",
                operator=misattribute_result_to_patient,
                contract=contract,
            )
        )
        index += 1
        seed += 1

    # CORRUPTION: 64, balanced across eight independent mutation operators.
    corruption_operators: tuple[
        tuple[str, Callable[[dict[str, Any]], MutatedGraph]], ...
    ] = (
        ("corrupt_numeric_value", corrupt_numeric_value),
        ("corrupt_unit_without_conversion", corrupt_unit_without_conversion),
        ("corrupt_observation_code", corrupt_observation_code),
        ("corrupt_patient_identifier", corrupt_patient_identifier),
        ("shift_observation_time", shift_observation_time),
        ("corrupt_result_status", corrupt_result_status),
        ("corrupt_interpretation", corrupt_interpretation),
        ("corrupt_reference_range", corrupt_reference_range),
    )
    for operator_name, operator in corruption_operators:
        for _ in range(8):
            cases.append(
                _single_case(
                    case_index=index,
                    semantic_class="CORRUPTION",
                    scenario_id="LAB-001",
                    seed=seed,
                    operator_name=operator_name,
                    operator=operator,
                    contract=contract,
                )
            )
            index += 1
            seed += 1

    # MULTI_FAULT: exactly 100, cycling MF001–MF003 deterministically.
    multi_operators: tuple[
        tuple[str, Callable[[dict[str, Any]], MultiMutatedGraph]], ...
    ] = (
        ("value_plus_unit_joint_corruption", value_plus_unit_joint_corruption),
        ("patient_swap_plus_valid_result", patient_swap_plus_valid_result),
        ("omission_plus_fabricated_replacement", omission_plus_fabricated_replacement),
    )
    for multi_index in range(100):
        operator_name, operator = multi_operators[multi_index % len(multi_operators)]
        # MF003 requires at least two source observations so one required result
        # can be omitted while a different surviving observation seeds the
        # unsupported replacement. LAB-005 supplies that topology without
        # changing the mutation operator merely to satisfy batch generation.
        scenario_id = (
            "LAB-005"
            if operator_name == "omission_plus_fabricated_replacement"
            else "LAB-001"
        )
        cases.append(
            _multi_case(
                case_index=multi_index + 1,
                scenario_id=scenario_id,
                seed=seed,
                operator_name=operator_name,
                operator=operator,
                contract=contract,
            )
        )
        seed += 1

    return FaultBatch(
        schema_version="0.1.0",
        purpose="pre_freeze_development_seeded_fault_qualification",
        cases=tuple(cases),
        batch_sha256=_batch_digest(cases),
    )


def class_counts(batch: FaultBatch) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in batch.cases:
        counts[case.semantic_class] = counts.get(case.semantic_class, 0) + 1
    return dict(sorted(counts.items()))
