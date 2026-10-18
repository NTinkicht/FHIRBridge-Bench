from pathlib import Path

from fhirbridge.schema_validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "canonical" / "schema"


def test_lab_001_example_matches_canonical_graph_schema() -> None:
    problems = validate_document(
        ROOT / "canonical" / "examples" / "LAB-001-example.yaml",
        SCHEMA_DIR / "clinical_fact_graph.schema.yaml",
        extra_schema_directories=[SCHEMA_DIR],
    )
    assert problems == []
