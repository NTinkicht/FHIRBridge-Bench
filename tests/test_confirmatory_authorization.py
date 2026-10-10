from types import SimpleNamespace

import pytest

import fhirbridge.confirmatory_authorization as authorization


def _protocol() -> dict:
    return {
        "protocol_freeze": {"status": "frozen"},
        "gates": [
            {
                "gate_id": "A",
                "status": "passed",
                "blockers": [],
            },
            {
                "gate_id": "B",
                "status": "passed",
                "blockers": [],
            },
        ],
        "confirmatory_run_policy": {
            "allowed_when_all_protocol_gates_passed": True,
            "tooling_manifest_must_also_be_frozen": True,
            "no_confirmatory_model_inference_before_ready": True,
        },
    }


def _freeze_manifest() -> dict:
    hashes = {
        "reviewer_roster": "1" * 64,
        "case_assignment_manifest": "2" * 64,
        "analysis_preregistration": "3" * 64,
        "sample_size_preregistration": "4" * 64,
        "model_prompt_configuration": "5" * 64,
    }
    return {
        **{
            key: {"sha256": value}
            for key, value in hashes.items()
        },
        "instrument_component_manifest": {
            "sha256": "7" * 64,
        },
        "instrument_components": {
            "verifier": {"sha256": "a" * 64},
            "deterministic_baseline_renderer": {"sha256": "b" * 64},
        },
        "acceptance_gate": {
            "preregistration_sha256": "6" * 64,
        },
        "sealed_set": {
            "case_count": 2,
            "case_manifest_sha256": "8" * 64,
        },
    }


def _hashes() -> dict[str, str]:
    return {
        "reviewer_roster": "1" * 64,
        "case_assignment_manifest": "2" * 64,
        "analysis_preregistration": "3" * 64,
        "sample_size_preregistration": "4" * 64,
        "model_prompt_configuration": "5" * 64,
        "pilot_acceptance_preregistration": "6" * 64,
        "instrument_component_manifest": "7" * 64,
        "sealed_case_manifest": "8" * 64,
    }


def _component_hashes() -> dict[str, str]:
    return {
        "verifier": "a" * 64,
        "deterministic_baseline_renderer": "b" * 64,
    }


@pytest.fixture
def ready_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        authorization,
        "assess_freeze_readiness",
        lambda _: SimpleNamespace(
            ready=True,
            manifest_status="frozen",
            unresolved_paths=(),
            false_boolean_paths=(),
        ),
    )
    monkeypatch.setattr(
        authorization,
        "assess_presealed_freeze",
        lambda _: SimpleNamespace(blockers=()),
    )
    monkeypatch.setattr(
        authorization,
        "assess_reviewer_roster",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        authorization,
        "assess_case_assignment_manifest",
        lambda *_args, **_kwargs: SimpleNamespace(
            ready=True,
            blockers=(),
        ),
    )
    monkeypatch.setattr(
        authorization,
        "assess_analysis_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        authorization,
        "assess_sample_size_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        authorization,
        "assess_model_prompt_freeze",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        authorization,
        "assess_pilot_acceptance_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )


def _authorize(
    *,
    protocol: dict | None = None,
    freeze: dict | None = None,
    hashes: dict[str, str] | None = None,
    component_hashes: dict[str, str] | None = None,
    sealed_case_ids: set[str] | None = None,
):
    return authorization.assess_confirmatory_authorization(
        protocol_gates=protocol or _protocol(),
        tooling_manifest={},
        freeze_manifest=freeze or _freeze_manifest(),
        reviewer_roster={},
        case_assignment_manifest={},
        analysis_preregistration={},
        sample_size_preregistration={},
        model_prompt_configuration={},
        pilot_acceptance_preregistration={},
        actual_artifact_sha256=hashes or _hashes(),
        actual_component_sha256=component_hashes or _component_hashes(),
        sealed_case_ids=sealed_case_ids or {"C1", "C2"},
    )


def test_all_ready_bound_components_authorize_confirmatory_inference(
    ready_dependencies,
) -> None:
    result = _authorize()

    assert result.authorized
    assert result.blockers == ()


def test_any_unpassed_protocol_gate_blocks_authorization(
    ready_dependencies,
) -> None:
    protocol = _protocol()
    protocol["gates"][1] = {
        "gate_id": "B",
        "status": "blocked",
        "blockers": ["external_review_pending"],
    }

    result = _authorize(protocol=protocol)

    assert not result.authorized
    assert any("protocol gate is not passed: B" == item for item in result.blockers)
    assert any("still lists blocker items: B" in item for item in result.blockers)


def test_freeze_manifest_hash_mismatch_blocks_authorization(
    ready_dependencies,
) -> None:
    hashes = _hashes()
    hashes["model_prompt_configuration"] = "f" * 64

    result = _authorize(hashes=hashes)

    assert not result.authorized
    assert any(
        "SHA-256 mismatch for model_prompt_configuration" in item
        for item in result.blockers
    )


def test_missing_actual_bound_hash_blocks_authorization(
    ready_dependencies,
) -> None:
    hashes = _hashes()
    del hashes["analysis_preregistration"]

    result = _authorize(hashes=hashes)

    assert not result.authorized
    assert any(
        "actual artifact SHA-256 is missing: analysis_preregistration" == item
        for item in result.blockers
    )


def test_sealed_case_count_must_match_bound_case_ids(
    ready_dependencies,
) -> None:
    result = _authorize(sealed_case_ids={"C1"})

    assert not result.authorized
    assert "sealed case ID count does not match freeze manifest" in result.blockers


def test_protocol_freeze_top_level_status_must_be_frozen(
    ready_dependencies,
) -> None:
    protocol = _protocol()
    protocol["protocol_freeze"]["status"] = "blocked"

    result = _authorize(protocol=protocol)

    assert not result.authorized
    assert "protocol freeze status is not frozen" in result.blockers


def test_changed_instrument_component_blocks_authorization(
    ready_dependencies,
) -> None:
    components = _component_hashes()
    components["deterministic_baseline_renderer"] = "f" * 64

    result = _authorize(component_hashes=components)

    assert not result.authorized
    assert any(
        "component SHA-256 mismatch for deterministic_baseline_renderer" in item
        for item in result.blockers
    )


def test_changed_sealed_case_manifest_file_blocks_authorization(
    ready_dependencies,
) -> None:
    hashes = _hashes()
    hashes["sealed_case_manifest"] = "f" * 64

    result = _authorize(hashes=hashes)

    assert not result.authorized
    assert any(
        "SHA-256 mismatch for sealed_case_manifest" in item
        for item in result.blockers
    )


def test_missing_actual_component_hash_blocks_authorization(
    ready_dependencies,
) -> None:
    components = _component_hashes()
    del components["verifier"]

    result = _authorize(component_hashes=components)

    assert not result.authorized
    assert (
        "actual component SHA-256 is missing: verifier"
        in result.blockers
    )


def test_unfrozen_extra_component_blocks_authorization(
    ready_dependencies,
) -> None:
    components = _component_hashes()
    components["unexpected_component"] = "c" * 64

    result = _authorize(component_hashes=components)

    assert not result.authorized
    assert any(
        "contains unfrozen components: unexpected_component" in item
        for item in result.blockers
    )


def test_missing_component_from_actual_digest_set_blocks_authorization(
    ready_dependencies,
) -> None:
    components = _component_hashes()
    del components["deterministic_baseline_renderer"]

    result = _authorize(component_hashes=components)

    assert not result.authorized
    assert any(
        "missing frozen components: deterministic_baseline_renderer" in item
        for item in result.blockers
    )
