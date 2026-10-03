from pathlib import Path

import pytest
import yaml

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.schema_validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "canonical" / "schema"
GRAPH_SCHEMA = SCHEMA_DIR / "clinical_fact_graph.schema.yaml"

TEMPLATES = [f"LAB-{index:03d}" for index in range(1, 13)]


def _observation_facts(graph: dict) -> list[dict]:
    return [fact for fact in graph["facts"] if fact["fact_type"] == "observation"]


def test_generator_is_deterministic_for_same_seed() -> None:
    first = generate_lab_scenario("LAB-001", 42)
    second = generate_lab_scenario("LAB-001", 42)
    assert first == second


def test_generator_changes_identifiers_across_seeds() -> None:
    first = generate_lab_scenario("LAB-001", 42)
    second = generate_lab_scenario("LAB-001", 43)
    assert first["graph_id"] != second["graph_id"]
    assert first["facts"][0]["identifiers"] != second["facts"][0]["identifiers"]


def test_high_and_low_templates_encode_expected_interpretation() -> None:
    high = generate_lab_scenario("LAB-002", 7)
    low = generate_lab_scenario("LAB-003", 7)

    high_obs = _observation_facts(high)[0]
    low_obs = _observation_facts(low)[0]

    assert high_obs["attributes"]["interpretation"]["code"] == "H"
    assert high_obs["value"] > high_obs["attributes"]["reference_range"]["high"]
    assert low_obs["attributes"]["interpretation"]["code"] == "L"
    assert low_obs["value"] < low_obs["attributes"]["reference_range"]["low"]


def test_all_declared_templates_generate_schema_valid_graphs(tmp_path: Path) -> None:
    for index, template_id in enumerate(TEMPLATES, start=1):
        graph = generate_lab_scenario(template_id, 1000 + index)
        artifact = tmp_path / f"{template_id}.yaml"
        artifact.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")

        problems = validate_document(
            artifact,
            GRAPH_SCHEMA,
            extra_schema_directories=[SCHEMA_DIR],
        )
        assert problems == [], f"{template_id}: {problems}"


def test_simple_panel_contains_multiple_distinct_observations() -> None:
    panel = generate_lab_scenario("LAB-005", 50)
    observations = _observation_facts(panel)
    assert len(observations) >= 3
    assert len({obs["concept"]["code"] for obs in observations}) == len(observations)


def test_repeated_same_code_scenario_preserves_distinct_times() -> None:
    repeated = generate_lab_scenario("LAB-011", 51)
    observations = _observation_facts(repeated)
    assert len(observations) == 2
    assert len({obs["concept"]["code"] for obs in observations}) == 1
    assert len({obs["temporal"]["effective_start"] for obs in observations}) == 2


def test_identifier_namespace_scenario_has_multiple_patient_namespaces() -> None:
    graph = generate_lab_scenario("LAB-010", 52)
    patient = next(fact for fact in graph["facts"] if fact["fact_type"] == "patient_identity")
    assert len(patient["identifiers"]) == 2
    assert len({identifier["system"] for identifier in patient["identifiers"]}) == 2


def test_ambiguity_fixture_is_excluded_from_primary_endpoint() -> None:
    graph = generate_lab_scenario("LAB-012", 53)
    metadata = graph["scenario_metadata"]
    assert metadata["primary_endpoint_eligible"] is False
    assert metadata["contract_state"] == "INDETERMINATE"


def test_specimen_required_scenario_cannot_disable_specimen() -> None:
    with pytest.raises(ValueError, match="requires specimen context"):
        generate_lab_scenario("LAB-006", 54, include_specimen=False)
