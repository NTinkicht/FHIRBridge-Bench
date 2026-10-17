from pathlib import Path

from fhirbridge.schema_validation import load_yaml, validate_document

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_SCHEMA = ROOT / "verifier" / "schema" / "semantic_decision.schema.yaml"


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_semantic_decision_example_matches_schema() -> None:
    problems = validate_document(
        ROOT / "verifier" / "examples" / "decision_example.yaml",
        VERIFIER_SCHEMA,
    )
    assert problems == []


def test_semantic_decision_schema_requires_contract_rule_ids(tmp_path: Path) -> None:
    decision = load_yaml(ROOT / "verifier" / "examples" / "decision_example.yaml")
    del decision["contract"]["rule_ids"]

    invalid_path = tmp_path / "invalid-decision.yaml"
    _write_yaml(invalid_path, decision)
    problems = validate_document(invalid_path, VERIFIER_SCHEMA)

    assert problems
    assert any("rule_ids" in problem.message for problem in problems)


def test_primary_endpoint_decision_requires_at_least_one_real_rule(tmp_path: Path) -> None:
    decision = load_yaml(ROOT / "verifier" / "examples" / "decision_example.yaml")
    decision["contract"]["rule_ids"] = []

    invalid_path = tmp_path / "empty-rule-set.yaml"
    _write_yaml(invalid_path, decision)
    problems = validate_document(invalid_path, VERIFIER_SCHEMA)

    assert problems
    assert any("non-empty" in problem.message or "[]" in problem.message for problem in problems)


def test_nonendpoint_indeterminate_decision_may_have_empty_rule_set(tmp_path: Path) -> None:
    decision = load_yaml(ROOT / "verifier" / "examples" / "decision_example.yaml")
    decision["contract"]["rule_ids"] = []
    decision["classification"] = "INDETERMINATE"
    decision["primary_endpoint_eligible"] = False
    decision["error_subtype"] = None
    decision["severity"] = None
    decision["evidence"]["rationale_code"] = "DIMENSION_OUTSIDE_CONTRACT_SCOPE"

    path = tmp_path / "nonendpoint-indeterminate.yaml"
    _write_yaml(path, decision)
    problems = validate_document(path, VERIFIER_SCHEMA)

    assert problems == []
