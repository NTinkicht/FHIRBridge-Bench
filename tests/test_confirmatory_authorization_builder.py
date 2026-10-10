import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import yaml

_MODULE_PATH = Path("runs/build_confirmatory_authorization.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_confirmatory_authorization",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_SCHEMA = Path("runs/schema/confirmatory_authorization_record.schema.json")


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )


def _paths(tmp_path: Path) -> dict[str, Path]:
    result = {}
    names = (
        "protocol_gates",
        "tooling_manifest",
        "freeze_manifest",
        "reviewer_roster",
        "case_assignment",
        "analysis_preregistration",
        "sample_size",
        "model_config",
        "pilot_acceptance",
    )
    for index, name in enumerate(names):
        path = tmp_path / f"{name}.yaml"
        _write_yaml(path, {"fixture": index})
        result[name] = path
    component_file = tmp_path / "component.txt"
    component_file.write_text("frozen component bytes\n", encoding="utf-8")
    component_manifest = tmp_path / "instrument-components.yaml"
    _write_yaml(
        component_manifest,
        {
            "instrument_component_manifest": {
                "hash_method": "path_bound_sha256_manifest_v1",
            },
            "components": {
                "fixture_component": {
                    "artifact_id": "fixture-component",
                    "paths": ["component.txt"],
                }
            },
        },
    )
    result["instrument_component_manifest"] = component_manifest

    case_ids = tmp_path / "case-ids.json"
    case_ids.write_text(
        json.dumps(["CASE-002", "CASE-001"]) + "\n",
        encoding="utf-8",
    )
    result["sealed_case_ids"] = case_ids

    case_manifest = tmp_path / "sealed-case-manifest.json"
    case_manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {"case_id": "CASE-001"},
                    {"case_id": "CASE-002"},
                ]
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    result["sealed_case_manifest"] = case_manifest
    return result


def _build(
    paths: dict[str, Path],
    *,
    authorization_id: str = "AUTH-001",
) -> dict:
    return _MODULE.build_authorization_record(
        protocol_gates_path=paths["protocol_gates"],
        tooling_manifest_path=paths["tooling_manifest"],
        freeze_manifest_path=paths["freeze_manifest"],
        instrument_component_manifest_path=paths[
            "instrument_component_manifest"
        ],
        reviewer_roster_path=paths["reviewer_roster"],
        case_assignment_path=paths["case_assignment"],
        analysis_preregistration_path=paths["analysis_preregistration"],
        sample_size_path=paths["sample_size"],
        model_config_path=paths["model_config"],
        pilot_acceptance_path=paths["pilot_acceptance"],
        sealed_case_manifest_path=paths["sealed_case_manifest"],
        sealed_case_ids_path=paths["sealed_case_ids"],
        authorization_id=authorization_id,
        created_at="2026-10-20T16:00:00Z",
        repository_commit="abcdef1",
        repository_root=paths["instrument_component_manifest"].parent,
    )


def test_authorization_builder_hashes_inputs_and_case_set(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        _MODULE,
        "assess_confirmatory_authorization",
        lambda **_: SimpleNamespace(authorized=True, blockers=()),
    )

    record = _build(paths)

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)
    assert record["authorized"] is True
    assert record["blockers"] == []
    assert record["sealed_case_set"]["case_count"] == 2
    assert record["sealed_case_set"]["canonical_case_ids_sha256"] == (
        _MODULE._case_ids_sha256({"CASE-001", "CASE-002"})
    )
    assert record["input_artifacts"]["model_prompt_configuration_sha256"] == (
        _MODULE._sha256(paths["model_config"])
    )
    assert record["input_artifacts"][
        "instrument_component_manifest_sha256"
    ] == _MODULE._sha256(paths["instrument_component_manifest"])
    assert record["input_artifacts"]["sealed_case_manifest_sha256"] == (
        _MODULE._sha256(paths["sealed_case_manifest"])
    )
    assert record["sealed_case_set"]["manifest_file_sha256"] == (
        _MODULE._sha256(paths["sealed_case_manifest"])
    )
    assert set(record["instrument_component_sha256"]) == {"fixture_component"}


def test_authorization_builder_preserves_denial_blockers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        _MODULE,
        "assess_confirmatory_authorization",
        lambda **_: SimpleNamespace(
            authorized=False,
            blockers=("profile_not_qualified", "pilot_gate_not_frozen"),
        ),
    )

    record = _build(paths)

    assert record["authorized"] is False
    assert record["blockers"] == [
        "profile_not_qualified",
        "pilot_gate_not_frozen",
    ]


def test_case_set_hash_is_order_independent() -> None:
    first = _MODULE._case_ids_sha256({"CASE-001", "CASE-002"})
    second = _MODULE._case_ids_sha256({"CASE-002", "CASE-001"})

    assert first == second


def test_case_id_loader_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "case-ids.json"
    path.write_text(
        json.dumps(["CASE-001", "CASE-001"]) + "\n",
        encoding="utf-8",
    )

    try:
        _MODULE._load_case_ids(path)
    except ValueError as exc:
        assert "duplicate sealed case ID" in str(exc)
    else:
        raise AssertionError("duplicate sealed case IDs must be rejected")


def test_case_manifest_hash_is_independent_of_canonical_case_id_list(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        _MODULE,
        "assess_confirmatory_authorization",
        lambda **_: SimpleNamespace(authorized=True, blockers=()),
    )

    record = _build(paths)

    assert record["input_artifacts"]["sealed_case_manifest_sha256"] != (
        _MODULE._sha256(paths["sealed_case_ids"])
    )
    assert record["sealed_case_set"]["canonical_case_ids_sha256"] == (
        _MODULE._case_ids_sha256({"CASE-001", "CASE-002"})
    )
