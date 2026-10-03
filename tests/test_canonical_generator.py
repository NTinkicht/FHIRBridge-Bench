from pathlib import Path

import yaml

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.schema_validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "canonical" / "schema"
GRAPH_SCHEMA = SCHEMA_DIR / "clinical_fact_graph.schema.yaml"


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

    high_obs = next(fact for fact in high["facts"] if fact["fact_type"] == "observation")
    low_obs = next(fact for fact in low["facts"] if fact["fact_type"] == "observation")

    assert high_obs["attributes"]["interpretation"]["code"] == "H"
    assert high_obs["value"] > 99
    assert low_obs["attributes"]["interpretation"]["code"] == "L"
    assert low_obs["value"] < 70


def test_generated_graph_matches_canonical_schema(tmp_path: Path) -> None:
    graph = generate_lab_scenario("LAB-007", 1001)
    artifact = tmp_path / "generated.yaml"
    artifact.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")

    problems = validate_document(
        artifact,
        GRAPH_SCHEMA,
        extra_schema_directories=[SCHEMA_DIR],
    )
    assert problems == []
