from pathlib import Path

from fhirbridge.renderer_b_challenge import (
    build_renderer_b_challenge,
    challenge_manifest,
    write_renderer_b_challenge,
)


def test_renderer_b_challenge_is_deterministic_and_covers_all_scenarios() -> None:
    first = build_renderer_b_challenge()
    second = build_renderer_b_challenge()

    assert first == second
    assert len(first) == 12
    assert {case.scenario_id for case in first} == {
        f"LAB-{index:03d}" for index in range(1, 13)
    }
    assert len({case.graph_sha256 for case in first}) == 12


def test_renderer_b_challenge_contains_only_development_canonical_inputs() -> None:
    cases = build_renderer_b_challenge()

    assert all(case.graph["scenario_metadata"]["partition"] == "development" for case in cases)
    assert all(
        case.graph["scenario_metadata"]["synthetic_only"] is True
        for case in cases
    )
    lab_012 = next(case for case in cases if case.scenario_id == "LAB-012")
    assert lab_012.primary_endpoint_eligible is False
    assert lab_012.contract_state == "INDETERMINATE"


def test_renderer_b_manifest_explicitly_excludes_reference_outputs() -> None:
    manifest = challenge_manifest(build_renderer_b_challenge())

    assert manifest["contains_renderer_a_output"] is False
    assert manifest["contains_target_gold_serialization"] is False
    assert manifest["contains_verifier_decisions"] is False
    assert manifest["contains_fault_labels"] is False
    assert manifest["contains_order_context"] is True
    assert manifest["contract"]["version"] == "0.3.0"
    assert manifest["contract"]["freeze_status"] == "draft_not_frozen"
    assert manifest["hl7v2_order_projection_policy"].startswith("fail_closed")
    assert len(manifest["manifest_sha256"]) == 64


def test_renderer_b_challenge_writer_emits_only_inputs_and_manifest(
    tmp_path: Path,
) -> None:
    manifest = write_renderer_b_challenge(tmp_path)

    files = sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert files == [
        "inputs/RB-001.json",
        "inputs/RB-002.json",
        "inputs/RB-003.json",
        "inputs/RB-004.json",
        "inputs/RB-005.json",
        "inputs/RB-006.json",
        "inputs/RB-007.json",
        "inputs/RB-008.json",
        "inputs/RB-009.json",
        "inputs/RB-010.json",
        "inputs/RB-011.json",
        "inputs/RB-012.json",
        "manifest.json",
    ]
    assert manifest["cases"][0]["input_path"] == "inputs/RB-001.json"


def test_renderer_b_v03_challenge_authors_order_context_in_all_cases() -> None:
    cases = build_renderer_b_challenge()

    for case in cases:
        orders = [
            fact for fact in case.graph["facts"]
            if fact["fact_type"] == "order"
        ]
        reports = [
            fact for fact in case.graph["facts"]
            if fact["fact_type"] == "diagnostic_report"
        ]
        assert len(orders) == 1, case.scenario_id
        assert len(reports) == 1, case.scenario_id
        order_id = orders[0]["fact_id"]
        assert any(
            relation["relation_type"] == "based_on_order"
            and relation["target_fact_id"] == order_id
            for relation in reports[0]["relations"]
        ), case.scenario_id
