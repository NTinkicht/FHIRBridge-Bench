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


def _mutate_number_fields(
    artifact: str,
    *,
    orc_placer: str | None = None,
    obr_placer: str | None = None,
    filler: str | None = None,
) -> str:
    segments = artifact.strip("\r").split("\r")
    changed: list[str] = []
    for segment in segments:
        if segment.startswith("ORC|"):
            if orc_placer is not None:
                segment = _set_field(
                    segment, 2, f"{orc_placer}^urn:fhirbridge:lab-order"
                )
            if filler is not None:
                segment = _set_field(
                    segment, 3, f"{filler}^urn:fhirbridge:accession"
                )
        if segment.startswith("OBR|"):
            if obr_placer is not None:
                segment = _set_field(
                    segment, 2, f"{obr_placer}^urn:fhirbridge:lab-order"
                )
            if filler is not None:
                segment = _set_field(
                    segment, 3, f"{filler}^urn:fhirbridge:accession"
                )
        changed.append(segment)
    return "\r".join(changed) + "\r"


def _order_fabrications(source_graph: dict, contract: dict, artifact: str):
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact, artifact_id="development-order-identifier-case"
    )
    result = fhirbridge.verifier.classify_graph(
        source_graph["facts"],
        list(lifted.facts),
        policy=fhirbridge.verifier.compile_verification_policy(contract),
    )
    return (
        lifted,
        [
            decision
            for decision in result.decisions
            if decision.evidence.get("guard_id")
            == "ORDER_IDENTIFIER_SOURCE_GROUNDING_001"
        ],
    )


def test_authored_accession_in_filler_slot_is_not_called_fabricated() -> None:
    graph, contract, artifact = _message(9951)
    accession = next(
        fact["identifiers"][0]["value"]
        for fact in graph["facts"]
        if fact["fact_type"] == "diagnostic_report"
    )
    artifact = _mutate_number_fields(artifact, filler=accession)
    lifted, decisions = _order_fabrications(graph, contract, artifact)

    assert decisions == []
    target_order = next(fact for fact in lifted.facts if fact.fact_type == "order")
    assert any(
        item["value"] == accession and item["type"] == "filler"
        for item in target_order.semantic_payload["identifiers"]
    )


def test_invented_filler_still_fails_source_grounding() -> None:
    graph, contract, artifact = _message(9952)
    artifact = _mutate_number_fields(artifact, filler="XYZ-999999")
    _, decisions = _order_fabrications(graph, contract, artifact)
    assert len(decisions) == 1
    assert decisions[0].classification == "FABRICATION"
    assert "XYZ-999999" in decisions[0].evidence["unsupported_values"]


def test_invented_placer_is_lifted_and_flagged() -> None:
    graph, contract, artifact = _message(9953)
    artifact = _mutate_number_fields(
        artifact, orc_placer="XYZ-PLACER-01", obr_placer="XYZ-PLACER-01"
    )
    lifted, decisions = _order_fabrications(graph, contract, artifact)
    assert len(decisions) == 1
    assert "XYZ-PLACER-01" in decisions[0].evidence["unsupported_values"]
    target_order = next(fact for fact in lifted.facts if fact.fact_type == "order")
    assert any(
        value["value"] == "XYZ-PLACER-01" and value["type"] == "placer"
        for value in target_order.semantic_payload["identifiers"]
    )


def test_source_order_placer_and_report_accession_filler_remain_nonfabricated() -> None:
    graph, contract, artifact = _message(9954)
    order_identifier = next(
        fact["identifiers"][0]["value"]
        for fact in graph["facts"]
        if fact["fact_type"] == "order"
    )
    report_accession = next(
        fact["identifiers"][0]["value"]
        for fact in graph["facts"]
        if fact["fact_type"] == "diagnostic_report"
    )
    artifact = _mutate_number_fields(
        artifact, orc_placer=order_identifier,
        obr_placer=order_identifier, filler=report_accession
    )
    lifted, decisions = _order_fabrications(graph, contract, artifact)
    assert decisions == []
    target_order = next(fact for fact in lifted.facts if fact.fact_type == "order")
    assert {
        (item["value"], item["type"])
        for item in target_order.semantic_payload["identifiers"]
    } == {(order_identifier, "placer"), (report_accession, "filler")}


def test_patient_mrn_cannot_be_laundered_into_order_filler() -> None:
    graph, contract, artifact = _message(9955)
    patient_id = next(
        fact["identifiers"][0]["value"]
        for fact in graph["facts"]
        if fact["fact_type"] == "patient_identity"
    )
    artifact = _mutate_number_fields(artifact, filler=patient_id)
    _, decisions = _order_fabrications(graph, contract, artifact)
    assert len(decisions) == 1
    assert patient_id in decisions[0].evidence["unsupported_values"]


def test_order_guard_policy_only_admits_order_and_diagnostic_report_sources() -> None:
    _, contract, _ = _message(9956)
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    guard = next(
        item for item in policy.grounding_guards
        if item.guard_id == "ORDER_IDENTIFIER_SOURCE_GROUNDING_001"
    )
    assert guard.source_fact_type == "order"
    assert guard.additional_source_fact_types == ("diagnostic_report",)
    assert guard.additional_source_relation_type == "has_report"


def test_unrelated_report_accession_is_not_authorized_for_target_order() -> None:
    from copy import deepcopy

    graph, contract, artifact = _message(9957)
    unrelated_report = deepcopy(
        next(fact for fact in graph["facts"] if fact["fact_type"] == "diagnostic_report")
    )
    unrelated_report["fact_id"] = "unrelated-report-9957"
    unrelated_report["identifiers"][0]["value"] = "UNRELATED-ACCESSION-9957"
    graph["facts"].append(unrelated_report)
    artifact = _mutate_number_fields(artifact, filler="UNRELATED-ACCESSION-9957")

    _, decisions = _order_fabrications(graph, contract, artifact)
    assert len(decisions) == 1
    assert "UNRELATED-ACCESSION-9957" in decisions[0].evidence[
        "unsupported_values"
    ]


def test_additional_source_types_require_declared_relationship_scope() -> None:
    from copy import deepcopy

    _, contract, _ = _message(9958)
    altered = deepcopy(contract)
    altered["grounding_guards"][0].pop("additional_source_relation_type")
    try:
        fhirbridge.verifier.compile_verification_policy(altered)
    except ValueError as exc:
        assert "additional_source_relation_type" in str(exc)
    else:
        raise AssertionError("unscoped cross-fact provenance must not compile")


def test_obr2_only_is_preserved_without_orc_or_filler() -> None:
    _, _, artifact = _message(9959)
    segments = [
        line for line in artifact.split("\r")
        if line and not line.startswith("ORC|")
    ]
    mutated: list[str] = []
    for line in segments:
        if line.startswith("OBR|"):
            line = _set_field(line, 2, "PLACER-ONLY-9959^urn:fhirbridge:lab-order")
            line = _set_field(line, 3, "")
            line = _set_field(line, 16, "")
        mutated.append(line)
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        "\r".join(mutated) + "\r",
        artifact_id="obr2-only-development",
    )
    orders = [fact for fact in lifted.facts if fact.fact_type == "order"]
    assert lifted.metadata["order_count"] == 1
    assert len(orders) == 1
    assert orders[0].semantic_payload["identifiers"] == [
        {
            "system": "urn:fhirbridge:lab-order",
            "value": "PLACER-ONLY-9959",
            "type": "placer",
        }
    ]
