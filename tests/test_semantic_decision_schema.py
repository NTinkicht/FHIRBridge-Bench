from pathlib import Path

from fhirbridge.schema_validation import load_yaml, validate_document

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_SCHEMA = ROOT / "verifier" / "schema" / "semantic_decision.schema.yaml"


def test_semantic_decision_example_matches_schema() -> None:
    problems = validate_document(
        ROOT / "verifier" / "examples" / "decision_example.yaml",
        VERIFIER_SCHEMA,
    )
    assert problems == []


def test_semantic_decision_schema_requires_contract_rule(tmp_path: Path) -> None:
    decision = load_yaml(ROOT / "verifier" / "examples" / "decision_example.yaml")
    del decision["contract"]["rule_id"]

    invalid_path = tmp_path / "invalid-decision.yaml"
    import yaml

    invalid_path.write_text(yaml.safe_dump(decision, sort_keys=False), encoding="utf-8")
    problems = validate_document(invalid_path, VERIFIER_SCHEMA)

    assert problems
    assert any("rule_id" in problem.message for problem in problems)
