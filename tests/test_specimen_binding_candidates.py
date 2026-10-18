import yaml

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_EVIDENCE = "benchmark/specimen_binding_candidates.yaml"
_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"


def _evidence() -> dict:
    with open(_EVIDENCE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_generic_hl7_specimen_candidates_are_recorded_but_not_frozen() -> None:
    doc = _evidence()

    assert doc["specimen_binding_candidates"]["status"] == (
        "draft_external_review_and_profile_binding_required"
    )
    terminology = doc["authoritative_generic_terminology"]
    assert terminology["specimen_type"]["code_system_url"].endswith("/v2-0487")
    assert terminology["specimen_type"]["relevant_active_codes"]["SER"]["display"] == (
        "Serum"
    )
    assert terminology["collection_method"]["code_system_url"].endswith("/v2-0488")
    assert terminology["collection_method"]["relevant_active_codes"]["VENIP"][
        "display"
    ] == "Venipuncture"


def test_primary_specimen_source_is_unambiguous_serum() -> None:
    graph = fhirbridge.canonical.generate_primary_lab_scenario("LAB-006", 13006)
    specimen = next(fact for fact in graph["facts"] if fact["fact_type"] == "specimen")

    assert specimen["attributes"]["type_label"] == "serum"
    assert specimen["attributes"]["collection_method_label"] == "venipuncture"


def test_fhir_specimen_representation_stays_source_text_without_unfrozen_code() -> None:
    graph = fhirbridge.canonical.generate_primary_lab_scenario("LAB-006", 13007)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
        graph,
        contract=contract,
    )
    specimen = next(
        entry["resource"]
        for entry in rendered.artifact["entry"]
        if entry["resource"]["resourceType"] == "Specimen"
    )

    assert specimen["type"] == {"text": "serum"}
    assert specimen["collection"]["method"] == {"text": "venipuncture"}
    assert "coding" not in specimen["type"]
    assert "coding" not in specimen["collection"]["method"]


def test_v2_specimen_codes_remain_explicit_development_placeholders() -> None:
    graph = fhirbridge.canonical.generate_lab_scenario("LAB-006", 13008)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    spm = next(
        segment
        for segment in rendered.artifact.split("\r")
        if segment.startswith("SPM|")
    )
    fields = spm.split("|")

    assert fields[4].endswith("^FBR-SPEC")
    assert fields[7].endswith("^FBR-METHOD")

    evidence = _evidence()["current_renderer_a_development_behavior"]
    assert evidence["SPM_4"]["confirmatory_use"] == "prohibited"
    assert evidence["SPM_7"]["confirmatory_use"] == "prohibited"


def test_specimen_binding_freeze_requires_exact_profile_reconciliation() -> None:
    requirements = set(_evidence()["freeze_requirements"])

    assert "reconcile_SPM_4_binding_with_exact_Edition5_machine_profile" in requirements
    assert "reconcile_SPM_7_binding_with_exact_Edition5_machine_profile" in requirements
    assert (
        "replace_or_remove_development_FBR_SPEC_and_FBR_METHOD_before_confirmatory_runs"
        in requirements
    )
