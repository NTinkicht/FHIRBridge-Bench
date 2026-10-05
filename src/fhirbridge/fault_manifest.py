"""Reproducible manifests for seeded-fault qualification runs.

A fault manifest records how a qualification stimulus was constructed without
making the mutation layer depend on semantic-verifier decision logic. The
manifest is evidence about the experimental stimulus, not evidence that the
verifier's eventual classification is correct.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Literal

from .artifact_faults import ArtifactMutation
from .faults import SeededFault
from .multi_faults import MultiFault

MutationLevel = Literal["canonical", "artifact"]
StructuralExpectation = Literal[
    "expected_valid",
    "expected_invalid",
    "depends_on_target_profile",
]


@dataclass(frozen=True)
class FaultRunManifest:
    schema_version: str
    graph_id: str
    scenario_id: str
    fault_id: str
    mutation_level: MutationLevel
    mutation_operator: str
    expected_classifications: tuple[str, ...]
    expected_severity: str
    structural_validity_expectation: StructuralExpectation
    contract_id: str
    contract_version: str
    component_fault_ids: tuple[str, ...]
    affected_fact_ids: tuple[str, ...]
    target_paths: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable manifest with a deterministic SHA-256."""

        payload = asdict(self)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        payload["manifest_sha256"] = sha256(encoded).hexdigest()
        return payload


def _contract_identity(contract: dict[str, Any]) -> tuple[str, str]:
    header = contract.get("contract")
    if not isinstance(header, dict):
        raise ValueError("contract must contain a 'contract' mapping")
    contract_id = header.get("id")
    version = header.get("version")
    if not isinstance(contract_id, str) or not contract_id:
        raise ValueError("contract.id must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("contract.version must be a non-empty string")
    return contract_id, version


def _scenario_id(graph: dict[str, Any]) -> str:
    for fact in graph.get("facts", []):
        provenance = fact.get("provenance") if isinstance(fact, dict) else None
        if isinstance(provenance, dict):
            value = provenance.get("scenario_id")
            if isinstance(value, str) and value:
                return value
    value = graph.get("scenario_type")
    if isinstance(value, str) and value:
        return value
    return "unknown"


def _graph_id(graph: dict[str, Any]) -> str:
    value = graph.get("graph_id")
    if not isinstance(value, str) or not value:
        raise ValueError("graph.graph_id must be a non-empty string")
    return value


def _max_severity(severities: tuple[str, ...]) -> str:
    order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
    if not severities:
        return "UNKNOWN"
    return max(severities, key=lambda value: order.get(value, -1))


def manifest_for_seeded_fault(
    graph: dict[str, Any],
    fault: SeededFault,
    *,
    contract: dict[str, Any],
    mutation_operator: str,
    structural_validity_expectation: StructuralExpectation = "expected_valid",
) -> FaultRunManifest:
    """Build a manifest for a canonical single-fault mutation."""

    contract_id, contract_version = _contract_identity(contract)
    return FaultRunManifest(
        schema_version="0.1.0",
        graph_id=_graph_id(graph),
        scenario_id=_scenario_id(graph),
        fault_id=fault.fault_id,
        mutation_level="canonical",
        mutation_operator=mutation_operator,
        expected_classifications=(fault.expected_class,),
        expected_severity=fault.expected_severity,
        structural_validity_expectation=structural_validity_expectation,
        contract_id=contract_id,
        contract_version=contract_version,
        component_fault_ids=(fault.fault_id,),
        affected_fact_ids=fault.affected_fact_ids,
        target_paths=(),
        metadata={"mutation": fault.mutation},
    )


def manifest_for_multi_fault(
    graph: dict[str, Any],
    fault: MultiFault,
    *,
    contract: dict[str, Any],
    mutation_operator: str,
    structural_validity_expectation: StructuralExpectation = "expected_valid",
) -> FaultRunManifest:
    """Build a manifest for a canonical composed-fault mutation."""

    contract_id, contract_version = _contract_identity(contract)
    severities = tuple(component.expected_severity for component in fault.components)
    return FaultRunManifest(
        schema_version="0.1.0",
        graph_id=_graph_id(graph),
        scenario_id=_scenario_id(graph),
        fault_id=fault.fault_id,
        mutation_level="canonical",
        mutation_operator=mutation_operator,
        expected_classifications=fault.expected_resolution,
        expected_severity=_max_severity(severities),
        structural_validity_expectation=structural_validity_expectation,
        contract_id=contract_id,
        contract_version=contract_version,
        component_fault_ids=tuple(component.fault_id for component in fault.components),
        affected_fact_ids=fault.affected_fact_ids,
        target_paths=(),
        metadata={
            "component_mutations": tuple(component.mutation for component in fault.components)
        },
    )


def manifest_for_artifact_fault(
    graph: dict[str, Any],
    fault: ArtifactMutation,
    *,
    contract: dict[str, Any],
    mutation_operator: str,
) -> FaultRunManifest:
    """Build a manifest for a serialized target-artifact mutation."""

    contract_id, contract_version = _contract_identity(contract)
    structural_expectation: StructuralExpectation = (
        "expected_valid" if fault.structural_validity_expected else "expected_invalid"
    )
    return FaultRunManifest(
        schema_version="0.1.0",
        graph_id=_graph_id(graph),
        scenario_id=_scenario_id(graph),
        fault_id=fault.fault_id,
        mutation_level="artifact",
        mutation_operator=mutation_operator,
        expected_classifications=(fault.expected_classification,),
        expected_severity=fault.expected_severity,
        structural_validity_expectation=structural_expectation,
        contract_id=contract_id,
        contract_version=contract_version,
        component_fault_ids=(fault.fault_id,),
        affected_fact_ids=(),
        target_paths=(fault.target_path,),
        metadata={"description": fault.description},
    )
