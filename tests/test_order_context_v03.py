from copy import deepcopy

import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
_CONTRACT_SCHEMA = "contracts/schema/projectability_contract.schema.yaml"


def _case(seed: int = 9911):
    graph = fhirbridge.canonical.generate_lab_scenario(
        "LAB-001",
        seed,
        include_order_context=True,
    )
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
        graph,
        contract=contract,
    )
    lifted = fhirbridge.lifters.FhirR4LabLifter().lift(
        rendered.artifact,
        artifact_id=f"order-{seed}-fhir-a",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )
    return graph, contract, rendered, lifted, result


def _resource(rendered, resource_type: str) -> dict:
    return next(
        entry["resource"]
        for entry in rendered.artifact["entry"]
        if entry["resource"]["resourceType"] == resource_type
    )


def test_contract_v03_conforms_to_projectability_schema() -> None:
    problems = fhirbridge.schema_validation.validate_document(
        _CONTRACT,
        _CONTRACT_SCHEMA,
    )

    assert problems == []


def test_order_context_is_authored_without_real_world_provider_identifier() -> None:
    graph, _, _, _, _ = _case(9912)
    order = next(fact for fact in graph["facts"] if fact["fact_type"] == "order")

    assert order["identifiers"][0]["system"] == "urn:fhirbridge:lab-order"
    requester = order["attributes"]["requester"]
    assert requester["identifier"]["system"] == "urn:fhirbridge:provider"
    assert requester["identifier"]["value"].startswith("PROV-")
    assert "npi" not in requester["identifier"]["system"].lower()


def test_fhir_order_context_uses_service_request_and_diagnostic_report_based_on() -> None:
    graph, _, rendered, lifted, result = _case(9913)
    order = next(fact for fact in graph["facts"] if fact["fact_type"] == "order")
    service_request = _resource(rendered, "ServiceRequest")
    report = _resource(rendered, "DiagnosticReport")

    assert service_request["meta"]["profile"] == [
        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-servicerequest"
    ]
    assert service_request["identifier"][0]["value"] == order["identifiers"][0]["value"]
    assert service_request["requester"]["identifier"]["system"] == (
        "urn:fhirbridge:provider"
    )
    assert report["basedOn"] == [
        {"reference": f"ServiceRequest/{service_request['id']}"}
    ]

    lifted_order = next(fact for fact in lifted.facts if fact.fact_type == "order")
    lifted_report = next(
        fact for fact in lifted.facts if fact.fact_type == "diagnostic_report"
    )
    assert (
        lifted_order.semantic_payload["identifiers"][0]["value"]
        == order["identifiers"][0]["value"]
    )
    assert any(
        relation_type == "based_on_order"
        and target_id == lifted_order.lifted_fact_id
        for relation_type, target_id in lifted_report.relationships
    )
    assert result.primary_endpoint_verdict == "FAITHFUL"


def test_extra_target_order_identifier_is_primary_fabrication() -> None:
    graph, contract, rendered, _, _ = _case(9914)
    mutated = deepcopy(rendered.artifact)
    service_request = next(
        entry["resource"]
        for entry in mutated["entry"]
        if entry["resource"]["resourceType"] == "ServiceRequest"
    )
    service_request["identifier"].append(
        {
            "system": "urn:fhirbridge:invented-order",
            "value": "FABRICATED-ORDER-9914",
        }
    )

    lifted = fhirbridge.lifters.FhirR4LabLifter().lift(
        mutated,
        artifact_id="fabricated-order-identifier",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )

    guard_decisions = [
        decision
        for decision in result.decisions
        if decision.evidence.get("guard_id")
        == "ORDER_IDENTIFIER_SOURCE_GROUNDING_001"
    ]
    assert len(guard_decisions) == 1
    assert guard_decisions[0].classification == "FABRICATION"
    assert guard_decisions[0].primary_endpoint_eligible
    assert guard_decisions[0].evidence["unsupported_values"] == [
        "FABRICATED-ORDER-9914"
    ]
    assert result.primary_endpoint_verdict == "UNFAITHFUL"


def test_order_mapping_questions_remain_indeterminate_in_v03() -> None:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    order_rules = {
        rule["rule_id"]: rule
        for rule in contract["rules"]
        if rule["rule_id"].startswith("ORDER_")
        or rule["rule_id"] == "REPORT_BASEDON_ORDER_001"
    }

    assert order_rules
    assert {
        rule["projectability"] for rule in order_rules.values()
    } == {"INDETERMINATE"}
    assert {
        rule["status"] for rule in order_rules.values()
    } == {"indeterminate"}
