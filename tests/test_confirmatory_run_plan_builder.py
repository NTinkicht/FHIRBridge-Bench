import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_MODULE_PATH = Path("runs/build_confirmatory_run_plan.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_confirmatory_run_plan",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_SCHEMA = Path("runs/schema/confirmatory_run_plan.schema.json")
_MODEL_TEMPLATE = Path("models/examples/model_prompt_freeze_template.yaml")


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )


def _artifact(character: str) -> dict:
    return {
        "path_or_ref": f"frozen/{character}.txt",
        "sha256": character * 64,
    }


def _model(key: str) -> dict:
    return {
        "model_key": key,
        "provider": "provider-x",
        "model_id": f"model-{key}",
        "model_revision_or_snapshot": f"snapshot-{key}",
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 4096,
        "seed_policy": "fixed_supported_seed",
        "seed": 20261020,
        "structured_output_mode": "json_schema",
    }


def _ready_model_config() -> dict:
    document = yaml.safe_load(_MODEL_TEMPLATE.read_text(encoding="utf-8"))
    document["config_id"] = "MODEL-FREEZE-001"
    document["status"] = "frozen"
    document["created_at"] = "2026-10-20T13:00:00Z"
    document["global_execution_policy"]["policy_artifact"] = {
        "path_or_ref": "models/execution_policy.yaml",
        "sha256": "e" * 64,
    }
    document["deterministic_baseline"]["implementation_artifact"] = _artifact(
        "1"
    )
    document["llm_models"] = [_model("M1"), _model("M2")]
    for index, strategy in enumerate(document["llm_strategies"], start=2):
        strategy["implementation_artifact"] = _artifact(str(index))
        if strategy["strategy_id"] == "direct_structured_llm":
            strategy["prompt_artifacts"] = [_artifact("5")]
        else:
            strategy["prompt_artifacts"] = [_artifact("6")]
            strategy["mapping_context_artifacts"] = [_artifact("8")]
        if (
            strategy["strategy_id"]
            == "mapping_aware_plus_syntax_repair"
        ):
            strategy["syntax_repair"]["implementation_artifact"] = _artifact(
                "9"
            )
    return document


def _fixture_paths(tmp_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for name in (
        "freeze_manifest",
        "protocol_gates",
        "tooling_manifest",
        "analysis_preregistration",
        "sample_size",
        "pilot_acceptance",
    ):
        path = tmp_path / f"{name}.yaml"
        _write_yaml(path, {"fixture": name})
        paths[name] = path

    model = tmp_path / "model-config.yaml"
    _write_yaml(model, _ready_model_config())
    paths["model_config"] = model

    bundle = tmp_path / "sealed.zip"
    bundle.write_bytes(b"sealed-bundle")
    paths["sealed_bundle"] = bundle

    case_manifest = tmp_path / "sealed-case-manifest.json"
    case_manifest.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "manifest_id": "SEALED-CASES-001",
                "status": "sealed",
                "created_at": "2026-10-20T15:30:00Z",
                "split": "sealed_test",
                "case_count": 2,
                "cases": [
                    {
                        "case_id": "C1",
                        "scenario_family": "LAB-001",
                        "analysis_cluster_id": "SOURCE-C1",
                        "source_input_sha256": "1" * 64,
                        "canonical_graph_sha256": "2" * 64,
                    },
                    {
                        "case_id": "C2",
                        "scenario_family": "LAB-006",
                        "analysis_cluster_id": "SOURCE-C2",
                        "source_input_sha256": "3" * 64,
                        "canonical_graph_sha256": "4" * 64,
                    },
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["sealed_case_manifest"] = case_manifest

    component_manifest = tmp_path / "instrument-components.yaml"
    _write_yaml(
        component_manifest,
        {
            "instrument_component_manifest": {"version": "0.1.0"},
            "components": {"verifier": {"path": "verifier.py"}},
        },
    )
    paths["instrument_component_manifest"] = component_manifest

    _write_yaml(
        paths["freeze_manifest"],
        {
            "sealed_set": {
                "bundle_id": "SEALED-001",
                "bundle_sha256": _MODULE._sha256(bundle),
                "case_manifest_sha256": _MODULE._sha256(case_manifest),
                "case_count": 2,
            },
            "instrument_components": {
                "deterministic_baseline_renderer": {
                    "sha256": "d" * 64,
                }
            },
        },
    )
    return paths


def _authorization(paths: dict[str, Path]) -> dict:
    case_ids = {"C1", "C2"}
    return {
        "schema_version": "0.2.0",
        "authorization_id": "AUTH-001",
        "created_at": "2026-10-20T16:00:00Z",
        "repository_commit": "abcdef1",
        "authorized": True,
        "blockers": [],
        "input_artifacts": {
            "protocol_freeze_gates_sha256": _MODULE._sha256(
                paths["protocol_gates"]
            ),
            "tooling_manifest_sha256": _MODULE._sha256(
                paths["tooling_manifest"]
            ),
            "freeze_manifest_sha256": _MODULE._sha256(
                paths["freeze_manifest"]
            ),
            "reviewer_roster_sha256": "1" * 64,
            "case_assignment_manifest_sha256": "2" * 64,
            "analysis_preregistration_sha256": _MODULE._sha256(
                paths["analysis_preregistration"]
            ),
            "sample_size_preregistration_sha256": _MODULE._sha256(
                paths["sample_size"]
            ),
            "model_prompt_configuration_sha256": _MODULE._sha256(
                paths["model_config"]
            ),
            "pilot_acceptance_preregistration_sha256": _MODULE._sha256(
                paths["pilot_acceptance"]
            ),
            "instrument_component_manifest_sha256": _MODULE._sha256(
                paths["instrument_component_manifest"]
            ),
            "sealed_case_manifest_sha256": _MODULE._sha256(
                paths["sealed_case_manifest"]
            ),
        },
        "instrument_component_sha256": {
            "verifier": "a" * 64,
        },
        "sealed_case_set": {
            "case_count": 2,
            "canonical_case_ids_sha256": _MODULE._case_ids_sha256(case_ids),
            "manifest_file_sha256": _MODULE._sha256(
                paths["sealed_case_manifest"]
            ),
        },
    }


def _write_authorization(
    tmp_path: Path,
    paths: dict[str, Path],
    *,
    authorized: bool = True,
) -> Path:
    record = _authorization(paths)
    if not authorized:
        record["authorized"] = False
        record["blockers"] = ["not_ready"]
    path = tmp_path / "authorization.json"
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _build(tmp_path: Path, paths: dict[str, Path]) -> dict:
    authorization = _write_authorization(tmp_path, paths)
    return _MODULE.build_run_plan(
        authorization_record_path=authorization,
        freeze_manifest_path=paths["freeze_manifest"],
        protocol_gates_path=paths["protocol_gates"],
        tooling_manifest_path=paths["tooling_manifest"],
        model_config_path=paths["model_config"],
        analysis_preregistration_path=paths["analysis_preregistration"],
        sample_size_path=paths["sample_size"],
        pilot_acceptance_path=paths["pilot_acceptance"],
        sealed_bundle_path=paths["sealed_bundle"],
        sealed_case_manifest_path=paths["sealed_case_manifest"],
        sealed_bundle_id="SEALED-001",
        run_plan_id="RUN-PLAN-001",
        created_at="2026-10-20T17:00:00Z",
        repository_commit="abcdef1",
    )


def test_run_plan_assembler_derives_counts_and_schema_bindings(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)

    plan = _build(tmp_path, paths)

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)
    assert plan["status"] == "prepared_authorized"
    assert plan["model_keys"] == ["M1", "M2"]
    assert plan["sealed_set"]["case_count"] == 2
    assert plan["expected_execution_counts"] == {
        "provider_generation_calls": 8,
        "derived_repair_outputs": 4,
        "deterministic_baseline_outputs": 2,
        "total_arm_outputs": 14,
    }
    assert plan["execution_record_contract"]["schema_version"] == "0.3.0"
    assert plan["authorization"]["record_schema_version"] == "0.2.0"
    assert plan["authorization"]["record_schema_sha256"] == _MODULE._sha256(
        _MODULE._AUTH_SCHEMA
    )
    assert plan["frozen_artifacts"][
        "deterministic_baseline_renderer_sha256"
    ] == "d" * 64
    assert plan["frozen_artifacts"][
        "deterministic_baseline_execution_schema_sha256"
    ] == _MODULE._sha256(_MODULE._BASELINE_EXECUTION_SCHEMA)


def test_run_plan_assembler_rejects_artifact_changed_after_authorization(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(tmp_path, paths)
    paths["analysis_preregistration"].write_text(
        "fixture: changed-after-authorization\n",
        encoding="utf-8",
    )

    try:
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-001",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )
    except ValueError as exc:
        assert "changed after authorization" in str(exc)
    else:
        raise AssertionError("post-authorization artifact mutation must fail")


def test_run_plan_assembler_rejects_changed_sealed_case_set(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(tmp_path, paths)
    manifest = json.loads(
        paths["sealed_case_manifest"].read_text(encoding="utf-8")
    )
    manifest["cases"][1]["case_id"] = "C3"
    paths["sealed_case_manifest"].write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    try:
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-001",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )
    except ValueError as exc:
        assert "sealed case identity set changed" in str(exc)
    else:
        raise AssertionError("changed sealed case set must fail")


def test_run_plan_assembler_rejects_denied_authorization(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(
        tmp_path,
        paths,
        authorized=False,
    )

    try:
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-001",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )
    except ValueError as exc:
        assert "does not authorize inference" in str(exc)
    else:
        raise AssertionError("denied authorization must never produce run plan")


def test_run_plan_assembler_rejects_sealed_bundle_changed_after_freeze(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(tmp_path, paths)
    paths["sealed_bundle"].write_bytes(b"changed-sealed-bundle")

    with pytest.raises(ValueError, match="sealed bundle bytes"):
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-001",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )


def test_run_plan_assembler_rejects_wrong_sealed_bundle_id(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(tmp_path, paths)

    with pytest.raises(ValueError, match="bundle ID"):
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-WRONG",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )


def test_run_plan_assembler_rejects_case_manifest_changed_after_authorization(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)
    authorization = _write_authorization(tmp_path, paths)
    manifest = json.loads(
        paths["sealed_case_manifest"].read_text(encoding="utf-8")
    )
    manifest["cases"][0]["source_input_sha256"] = "f" * 64
    paths["sealed_case_manifest"].write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="case manifest changed"):
        _MODULE.build_run_plan(
            authorization_record_path=authorization,
            freeze_manifest_path=paths["freeze_manifest"],
            protocol_gates_path=paths["protocol_gates"],
            tooling_manifest_path=paths["tooling_manifest"],
            model_config_path=paths["model_config"],
            analysis_preregistration_path=paths["analysis_preregistration"],
            sample_size_path=paths["sample_size"],
            pilot_acceptance_path=paths["pilot_acceptance"],
            sealed_bundle_path=paths["sealed_bundle"],
            sealed_case_manifest_path=paths["sealed_case_manifest"],
                sealed_bundle_id="SEALED-001",
            run_plan_id="RUN-PLAN-001",
            created_at="2026-10-20T17:00:00Z",
            repository_commit="abcdef1",
        )
