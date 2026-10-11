"""Development stress case: ordered test and reported test need not be identical."""

import yaml

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.lifters import FhirR4LabLifter
from fhirbridge.renderers import FhirR4LabRendererA
from fhirbridge.verifier import classify_graph, compile_verification_policy

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"


def test_distinct_service_request_and_diagnostic_report_codes_survive_fhir_path() -> None:
    graph = generate_lab_scenario(
        "LAB-001", 9961, include_order_context=True
    )
    order = next(f for f in graph["facts"] if f["fact_type"] == "order")
    report = next(f for f in graph["facts"] if f["fact_type"] == "diagnostic_report")
    order["concept"] = {
        "system": "http://loinc.org",
        "code": "2345-7",
        "display": "Glucose [Mass/volume] in Serum or Plasma",
        "local_code": None,
    }
    assert order["concept"]["code"] != report["concept"]["code"]

    with open(_CONTRACT, encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    output = FhirR4LabRendererA().render(graph, contract=contract).artifact
    resources = {
        entry["resource"]["resourceType"]: entry["resource"]
        for entry in output["entry"]
    }

    order_code = resources["ServiceRequest"]["code"]["coding"][0]["code"]
    report_code = resources["DiagnosticReport"]["code"]["coding"][0]["code"]
    assert order_code == "2345-7"
    assert report_code == "24323-8"
    assert order_code != report_code

    lifted = FhirR4LabLifter().lift(
        output, artifact_id="candidate-nonidentical-order-report-codes"
    )
    lifted_order = next(f for f in lifted.facts if f.fact_type == "order")
    lifted_report = next(f for f in lifted.facts if f.fact_type == "diagnostic_report")
    assert lifted_order.semantic_payload["concept"]["code"] == order_code
    assert lifted_report.semantic_payload["concept"]["code"] == report_code

    result = classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=compile_verification_policy(contract),
    )
    assert result.primary_endpoint_verdict == "FAITHFUL"

    decisions = {
        rule["rule_id"]: rule["projectability"] for rule in contract["rules"]
    }
    assert decisions["ORDER_CODE_MAPPING_001"] == "INDETERMINATE"
    assert decisions["REPORT_CODE_001"] == "MUST_PRESERVE"
