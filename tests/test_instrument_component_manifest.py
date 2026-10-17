from pathlib import Path

import yaml

_MANIFEST = Path("benchmark/instrument_component_manifest.yaml")


def _manifest() -> dict:
    return yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))


def test_instrument_component_boundary_is_explicitly_frozen() -> None:
    document = _manifest()

    assert document["instrument_component_manifest"]["status"] == (
        "frozen_component_boundary"
    )
    assert document["instrument_component_manifest"]["hash_method"] == (
        "path_bound_sha256_manifest_v1"
    )


def test_verifier_bundle_enumerates_every_verifier_python_module() -> None:
    document = _manifest()
    configured = set(document["components"]["verifier"]["paths"])
    actual = {
        path.as_posix()
        for path in Path("src/fhirbridge/verifier").glob("*.py")
    }

    assert configured == actual


def test_lifter_bundles_include_shared_base_and_verifier_model() -> None:
    document = _manifest()

    for component in ("fhir_lifter", "hl7v2_lifter"):
        paths = set(document["components"][component]["paths"])
        assert "src/fhirbridge/lifters/__init__.py" in paths
        assert "src/fhirbridge/lifters/base.py" in paths
        assert "src/fhirbridge/verifier/model.py" in paths

    assert "src/fhirbridge/lifters/fhir_r4.py" in set(
        document["components"]["fhir_lifter"]["paths"]
    )
    assert "src/fhirbridge/lifters/hl7v251_oru.py" in set(
        document["components"]["hl7v2_lifter"]["paths"]
    )


def test_canonical_schema_bundle_includes_graph_and_fact_schema() -> None:
    document = _manifest()
    paths = set(document["components"]["canonical_schema"]["paths"])

    assert paths == {
        "canonical/schema/clinical_fact.schema.yaml",
        "canonical/schema/clinical_fact_graph.schema.yaml",
    }


def test_final_measurement_policy_bundles_never_point_to_candidates() -> None:
    document = _manifest()

    assert document["components"]["severity_policy"]["paths"] == [
        "benchmark/severity_policy_frozen.yaml"
    ]
    assert document["components"]["precedence_policy"]["paths"] == [
        "benchmark/error_precedence_policy_frozen.yaml"
    ]


def test_deterministic_baseline_bundle_matches_imported_renderer_package() -> None:
    document = _manifest()
    configured = set(
        document["components"]["deterministic_baseline_renderer"]["paths"]
    )
    actual = {
        path.as_posix()
        for path in Path("src/fhirbridge/renderers").glob("*.py")
    }

    assert configured == actual
    assert "src/fhirbridge/renderers/hl7v251_oru_a.py" in configured
