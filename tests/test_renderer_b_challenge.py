from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from fhirbridge.renderer_b_challenge import (
    _document_sha256,
    build_renderer_b_challenge,
    challenge_manifest,
    validate_renderer_b_challenge_inputs,
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


def _changed_case_graph(*, extra_key: str, value):
    cases = list(build_renderer_b_challenge())
    graph = deepcopy(cases[0].graph)
    # Attach at the deepest nested record to catch inadvertent source/gold
    # leakage from a future canonical generator, not just top-level metadata.
    graph["facts"][0][extra_key] = value
    cases[0] = replace(
        cases[0], graph=graph, graph_sha256=_document_sha256(graph)
    )
    return tuple(cases)


@pytest.mark.parametrize(
    "key",
    [
        "renderer_a_output",
        "Renderer-A-Output",
        "target_gold_serialization",
        "expected_fhir",
        "expected_hl7v2",
        "verifier_decisions",
        "semantic_verifier_result",
        "fault_label",
        "sealed_test_data",
        "answer_key",
    ],
)
def test_reference_outputs_cannot_enter_renderer_b_challenge(key: str) -> None:
    modified = _changed_case_graph(
        extra_key=key,
        value={"nested": ["SYNTHETIC REFERENCE ANSWER; NOT A REAL OUTPUT"]},
    )
    with pytest.raises(ValueError, match="prohibited reference or answer field"):
        challenge_manifest(modified)


def test_nested_reference_contamination_is_rejected() -> None:
    modified = _changed_case_graph(
        extra_key="extension", value={"inner": [{"gold_output": "FAKE"}]}
    )
    with pytest.raises(ValueError, match="prohibited reference or answer field"):
        validate_renderer_b_challenge_inputs(modified)


def test_non_synthetic_and_non_development_graphs_fail_closed() -> None:
    for change in (
        {"synthetic_only": False},
        {"partition": "confirmatory"},
    ):
        cases = list(build_renderer_b_challenge())
        graph = deepcopy(cases[0].graph)
        graph["scenario_metadata"].update(change)
        cases[0] = replace(
            cases[0], graph=graph, graph_sha256=_document_sha256(graph)
        )
        with pytest.raises(ValueError, match="synthetic development data only"):
            challenge_manifest(tuple(cases))


def test_changed_graph_after_hashing_fails_closed() -> None:
    cases = list(build_renderer_b_challenge())
    cases[0].graph["facts"][0]["answer_key"] = "FAKE"
    with pytest.raises(ValueError, match="hash no longer matches"):
        validate_renderer_b_challenge_inputs(tuple(cases))


def test_duplicate_or_missing_challenge_case_is_rejected() -> None:
    cases = build_renderer_b_challenge()
    with pytest.raises(ValueError, match="exactly 12"):
        challenge_manifest(cases[:-1])
    with pytest.raises(ValueError, match="duplicate case IDs"):
        challenge_manifest(cases[:-1] + (replace(cases[-1], case_id=cases[0].case_id),))


def test_writer_rejects_contamination_before_creating_output_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fhirbridge import renderer_b_challenge

    contaminated = _changed_case_graph(
        extra_key="fault_labels", value=["SYNTHETIC FAKE"]
    )
    monkeypatch.setattr(
        renderer_b_challenge, "build_renderer_b_challenge", lambda: contaminated
    )
    output = tmp_path / "new_clean_room_handoff"
    with pytest.raises(ValueError, match="prohibited reference or answer field"):
        write_renderer_b_challenge(output)
    assert not output.exists()
