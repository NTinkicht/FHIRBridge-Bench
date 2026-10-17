from copy import deepcopy

import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier
from fhirbridge.artifact_faults import (
    misattribute_observation_to_report,
    swap_specimen_identifiers,
)
from fhirbridge.structural import Hl7V251OruDevelopmentValidator

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _merge_graphs(
    first_template: str,
    first_seed: int,
    second_template: str,
    second_seed: int,
) -> dict:
    first = fhirbridge.canonical.generate_lab_scenario(first_template, first_seed)
    second = fhirbridge.canonical.generate_lab_scenario(second_template, second_seed)

    first_patient = next(
        fact for fact in first["facts"] if fact["fact_type"] == "patient_identity"
    )
    second_patient = next(
        fact for fact in second["facts"] if fact["fact_type"] == "patient_identity"
    )
    second_facts = deepcopy(
        [fact for fact in second["facts"] if fact["fact_type"] != "patient_identity"]
    )
    for fact in second_facts:
        if fact.get("subject_ref") == second_patient["fact_id"]:
            fact["subject_ref"] = first_patient["fact_id"]

    merged = deepcopy(first)
    merged["graph_id"] = (
        f"CFG-MERGED-{first_template}-{first_seed}-"
        f"{second_template}-{second_seed}"
    )
    merged["facts"].extend(second_facts)
    return merged


def _render(graph: dict) -> tuple[dict, str]:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    return contract, rendered.artifact


def test_f007_moves_intact_observation_to_wrong_report_group() -> None:
    graph = _merge_graphs("LAB-005", 9701, "LAB-001", 9702)
    contract, artifact = _render(graph)

    mutation = misattribute_observation_to_report(
        artifact,
        source_group=0,
        target_group=1,
        observation_occurrence=0,
    )

    assert mutation.fault_id == "F007"
    assert mutation.expected_classification == "MISATTRIBUTION"
    assert mutation.artifact.count("\rOBR|") == 2
    assert mutation.artifact.count("\rOBX|") == artifact.count("\rOBX|")

    structural = Hl7V251OruDevelopmentValidator().validate(mutation.artifact)
    assert structural.valid

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        mutation.artifact,
        artifact_id="F007-development",
    )
    development = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
    )
    assert not development.faithful
    assert any(
        decision.classification == "MISATTRIBUTION"
        and decision.evidence.get("rationale_code")
        == "WRONG_RELATIONSHIP_ATTRIBUTION"
        for decision in development.decisions
    )

    policy = fhirbridge.verifier.compile_verification_policy(contract)
    scoped = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )
    assert scoped.faithful
    assert all(
        decision.classification != "MISATTRIBUTION"
        for decision in scoped.decisions
    )


def test_f014_swaps_valid_specimen_ids_between_result_contexts() -> None:
    graph = _merge_graphs("LAB-006", 9711, "LAB-006", 9712)
    specimens = [fact for fact in graph["facts"] if fact["fact_type"] == "specimen"]
    assert len(specimens) == 2
    # Isolate attribution as the only changed semantic construct. If collection
    # times differ, the swapped identifier can legitimately surface first as a
    # temporal corruption under deterministic mismatch precedence.
    specimens[1]["temporal"] = deepcopy(specimens[0]["temporal"])
    _, artifact = _render(graph)

    mutation = swap_specimen_identifiers(artifact)

    assert mutation.fault_id == "F014"
    assert mutation.expected_classification == "MISATTRIBUTION"
    assert mutation.artifact.count("\rSPM|") == 2

    structural = Hl7V251OruDevelopmentValidator().validate(mutation.artifact)
    assert structural.valid

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        mutation.artifact,
        artifact_id="F014-development",
    )
    development = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
    )

    assert not development.faithful
    specimen_source_ids = {
        fact["fact_id"]
        for fact in graph["facts"]
        if fact["fact_type"] == "specimen"
    }
    misattributed_specimen_ids = {
        decision.source_fact_ids[0]
        for decision in development.decisions
        if decision.classification == "MISATTRIBUTION"
        and decision.source_fact_ids
        and decision.source_fact_ids[0] in specimen_source_ids
    }
    assert misattributed_specimen_ids
