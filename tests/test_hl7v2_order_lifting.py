import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"


def _set_field(segment: str, field_number: int, value: str) -> str:
    fields = segment.split("|")
    while len(fields) <= field_number:
        fields.append("")
    fields[field_number] = value
    return "|".join(fields)


def _xcn(provider_value: str) -> str:
    return f"{provider_value}^Provider^Synthetic^^^^^^urn:fhirbridge:provider"


def _message(
    seed: int,
    *,
    orc_identifier: str | None = None,
    obr_identifier: str | None = None,
    orc_provider: str | None = None,
    obr_provider: str | None = None,
) -> tuple[dict, dict, str]:
    source_graph = fhirbridge.canonical.generate_lab_scenario(
        "LAB-001",
        seed,
        include_order_context=True,
    )
    legacy_graph = fhirbridge.canonical.generate_lab_scenario("LAB-001", seed)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    base = fhirbridge.renderers.Hl7V251OruRendererA().render(
        legacy_graph,
        contract=contract,
    ).artifact

    order = next(fact for fact in source_graph["facts"] if fact["fact_type"] == "order")
    expected_order = order["identifiers"][0]["value"]
    expected_provider = order["attributes"]["requester"]["identifiers"][0]["value"]
    orc_identifier = orc_identifier or expected_order
    obr_identifier = obr_identifier or expected_order
    orc_provider = orc_provider or expected_provider
    obr_provider = obr_provider or expected_provider

    segments = [segment for segment in base.split("\r") if segment]
    obr_index = next(i for i, segment in enumerate(segments) if segment.startswith("OBR|"))
    obr = _set_field(segments[obr_index], 3, f"{obr_identifier}^urn:fhirbridge:lab-order")
    obr = _set_field(obr, 16, _xcn(obr_provider))
    segments[obr_index] = obr

    orc = "ORC|ZZ||" + f"{orc_identifier}^urn:fhirbridge:lab-order"
    orc = _set_field(orc, 12, _xcn(orc_provider))
    segments.insert(obr_index, orc)
    return source_graph, contract, "\r".join(segments) + "\r"


def test_v2_lifter_observes_order_identifier_and_requester_without_mapping_claim() -> None:
    source_graph, _, artifact = _message(9931)
    source_order = next(
        fact for fact in source_graph["facts"] if fact["fact_type"] == "order"
    )

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="v2-order-observation",
    )
    order = next(fact for fact in lifted.facts if fact.fact_type == "order")
    report = next(
        fact for fact in lifted.facts if fact.fact_type == "diagnostic_report"
    )

    assert [item["value"] for item in order.semantic_payload["identifiers"]] == [
        source_order["identifiers"][0]["value"]
    ]
    assert order.semantic_payload["attributes"]["requester"]["identifiers"][0][
        "value"
    ] == source_order["attributes"]["requester"]["identifiers"][0]["value"]
    assert ("has_report", report.lifted_fact_id) in order.relationships
    assert ("based_on_order", order.lifted_fact_id) in report.relationships
    assert lifted.metadata["order_count"] == 1


def test_v2_lifter_retains_conflicting_orc3_and_obr3_assertions() -> None:
    _, _, artifact = _message(
        9932,
        orc_identifier="SOURCE-LIKE-ORDER",
        obr_identifier="EXTRA-ORDER",
    )

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="v2-conflicting-filler-identifiers",
    )
    order = next(fact for fact in lifted.facts if fact.fact_type == "order")

    assert {item["value"] for item in order.semantic_payload["identifiers"]} == {
        "SOURCE-LIKE-ORDER",
        "EXTRA-ORDER",
    }


def test_v2_order_identifier_fabrication_guard_sees_extra_assertion() -> None:
    source_graph, contract, artifact = _message(
        9933,
        obr_identifier="FABRICATED-OBR3-9933",
    )
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="v2-fabricated-order",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        source_graph["facts"],
        list(lifted.facts),
        policy=policy,
    )

    decisions = [
        decision
        for decision in result.decisions
        if decision.evidence.get("guard_id")
        == "ORDER_IDENTIFIER_SOURCE_GROUNDING_001"
    ]
    assert len(decisions) == 1
    assert decisions[0].classification == "FABRICATION"
    assert "FABRICATED-OBR3-9933" in decisions[0].evidence["unsupported_values"]


def test_v2_requester_grounding_guard_sees_conflicting_obr16_provider() -> None:
    source_graph, contract, artifact = _message(
        9934,
        obr_provider="FABRICATED-PROVIDER-9934",
    )
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="v2-fabricated-provider",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        source_graph["facts"],
        list(lifted.facts),
        policy=policy,
    )

    decisions = [
        decision
        for decision in result.decisions
        if decision.evidence.get("guard_id")
        == "ORDER_REQUESTER_IDENTIFIER_SOURCE_GROUNDING_001"
    ]
    assert len(decisions) == 1
    assert decisions[0].classification == "FABRICATION"
    assert "FABRICATED-PROVIDER-9934" in decisions[0].evidence["unsupported_values"]
