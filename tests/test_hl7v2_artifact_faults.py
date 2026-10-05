import pytest

import fhirbridge.artifact_faults
import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.structural
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _source_and_artifact(seed: int):
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", seed)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        source,
        contract=contract,
    )
    return source, contract, rendered.artifact


def _classify(source: dict, contract: dict, artifact: str):
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id=f"{source['graph_id']}-artifact-fault",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    return fhirbridge.verifier.classify_graph(
        source["facts"],
        list(lifted.facts),
        policy=policy,
    )


def _classes(result) -> set[str]:
    return {decision.classification for decision in result.decisions}


def test_f009_report_time_omission_stays_structurally_valid_but_semantically_fails() -> None:
    source, contract, artifact = _source_and_artifact(9601)
    mutant = fhirbridge.artifact_faults.omit_report_issued_time(artifact)

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(
        mutant.artifact
    )
    semantic = _classify(source, contract, mutant.artifact)

    assert mutant.fault_id == "F009"
    assert mutant.expected_classification == "OMISSION"
    assert structural.valid
    assert not semantic.faithful
    assert "OMISSION" in _classes(semantic)
    report_omissions = [
        decision
        for decision in semantic.decisions
        if decision.classification == "OMISSION"
        and decision.evidence.get("omitted_field") == "temporal.recorded_at"
    ]
    assert report_omissions
    assert report_omissions[0].evidence["projectability"] == "MUST_PRESERVE"


def test_f016_unsupported_derived_assertion_is_valid_but_fabricated() -> None:
    source, contract, artifact = _source_and_artifact(9602)
    mutant = fhirbridge.artifact_faults.add_unauthorized_derived_observation(artifact)

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(
        mutant.artifact
    )
    semantic = _classify(source, contract, mutant.artifact)

    assert mutant.fault_id == "F016"
    assert structural.valid
    assert not semantic.faithful
    assert "FABRICATION" in _classes(semantic)


def test_f018_structural_negative_control_is_intercepted_before_semantic_scoring() -> None:
    source, _, artifact = _source_and_artifact(9603)
    mutant = fhirbridge.artifact_faults.corrupt_message_version(artifact)

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(
        mutant.artifact
    )

    assert source["graph_id"]
    assert mutant.fault_id == "F018"
    assert not structural.valid
    assert "WRONG_VERSION" in {finding.code for finding in structural.findings}
    with pytest.raises(ValueError, match="requires version 2.5.1"):
        fhirbridge.lifters.Hl7V251OruLifter().lift(
            mutant.artifact,
            artifact_id="f018-negative-control",
        )
