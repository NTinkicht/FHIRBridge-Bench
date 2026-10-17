from copy import deepcopy

import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _two_report_graph() -> dict:
    left = fhirbridge.canonical.generate_lab_scenario("LAB-006", 9601)
    right = fhirbridge.canonical.generate_lab_scenario("LAB-006", 9602)

    left_patient = next(
        fact for fact in left["facts"] if fact["fact_type"] == "patient_identity"
    )
    right_patient = next(
        fact for fact in right["facts"] if fact["fact_type"] == "patient_identity"
    )
    right_facts = deepcopy(
        [fact for fact in right["facts"] if fact["fact_type"] != "patient_identity"]
    )
    for fact in right_facts:
        if fact.get("subject_ref") == right_patient["fact_id"]:
            fact["subject_ref"] = left_patient["fact_id"]

    graph = deepcopy(left)
    graph["graph_id"] = "CFG-LAB-TWO-REPORT-9601-9602"
    graph["facts"].extend(right_facts)
    return graph


def test_renderer_and_lifter_preserve_two_order_observation_groups() -> None:
    graph = _two_report_graph()
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)

    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    artifact = rendered.artifact

    assert artifact.count("\rOBR|") == 2
    assert artifact.count("\rSPM|") == 2
    assert artifact.count("\rOBX|") == 2
    assert rendered.manifest.metadata["report_count"] == 2
    assert rendered.manifest.metadata["specimen_count"] == 2

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="two-report-development-fixture",
    )

    reports = [
        fact for fact in lifted.facts if fact.fact_type == "diagnostic_report"
    ]
    observations = [
        fact for fact in lifted.facts if fact.fact_type == "observation"
    ]
    specimens = [
        fact for fact in lifted.facts if fact.fact_type == "specimen"
    ]

    assert lifted.metadata["report_count"] == 2
    assert lifted.metadata["specimen_count"] == 2
    assert lifted.metadata["observation_count"] == 2
    assert len({fact.lifted_fact_id for fact in reports}) == 2
    assert len({fact.lifted_fact_id for fact in observations}) == 2
    assert len({fact.lifted_fact_id for fact in specimens}) == 2

    for report in reports:
        assert len(
            [
                relation
                for relation in report.relationships
                if relation[0] == "has_result"
            ]
        ) == 1
        assert len(
            [
                relation
                for relation in report.relationships
                if relation[0] == "has_specimen"
            ]
        ) == 1

    for observation in observations:
        assert len(
            [
                relation
                for relation in observation.relationships
                if relation[0] == "belongs_to_report"
            ]
        ) == 1
        assert len(
            [
                relation
                for relation in observation.relationships
                if relation[0] == "specimen"
            ]
        ) == 1


def test_two_report_round_trip_remains_semantically_faithful() -> None:
    graph = _two_report_graph()
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    policy = fhirbridge.verifier.compile_verification_policy(contract)

    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        rendered.artifact,
        artifact_id="two-report-round-trip",
    )
    result = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )

    assert result.faithful
    assert result.primary_endpoint_verdict == "FAITHFUL"
    assert all(
        decision.classification != "INDETERMINATE"
        for decision in result.decisions
    )
