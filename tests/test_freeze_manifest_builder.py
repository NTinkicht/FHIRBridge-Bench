import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import yaml

_MODULE_PATH = Path("expert_validation/build_freeze_manifest.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_freeze_manifest",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_SCHEMA = Path("expert_validation/schema/freeze_manifest.schema.json")
_COMPONENT_NAMES = (
    "projectability_contract",
    "verifier",
    "fhir_lifter",
    "hl7v2_lifter",
    "canonical_schema",
    "deterministic_baseline_renderer",
    "severity_policy",
    "precedence_policy",
)


def _write_yaml(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _fixture(tmp_path: Path) -> dict[str, Path]:
    tooling = {
        "manifest": {"status": "frozen"},
        "terminology": {
            "loinc": {
                "content_version": "2.83",
                "qualification_report": "loinc.json",
                "local_snapshot_sha256": "1" * 64,
            },
            "hl7_terminology": {
                "version": "7.4.0",
                "package": "hl7.terminology",
                "package_sha256": "2" * 64,
            },
        },
        "units": {
            "ucum": {
                "content_version": "2.2",
                "essence_source": "ucum-essence.xml",
                "essence_sha256": "3" * 64,
            }
        },
        "structural_validation": {
            "fhir": {
                "validator_cli_version": "6.10.0",
                "validator_cli_artifact_source": "validator_cli.jar",
                "validator_cli_artifact_sha256": "4" * 64,
                "package_cache_manifest_sha256": "5" * 64,
            },
            "hl7v2": {
                "validator_version": "1.5.0",
                "validator_runtime_classpath_manifest": "validator-runtime.json",
                "validator_runtime_classpath_sha256": "6" * 64,
                "profile_artifact": "lri-ed5-bundle.zip",
                "profile_artifact_sha256": "7" * 64,
            },
        },
    }
    tooling_path = _write_yaml(tmp_path / "tooling.yaml", tooling)

    components = {}
    for index, name in enumerate(_COMPONENT_NAMES, start=1):
        path = tmp_path / f"components/{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}\n", encoding="utf-8")
        components[name] = {
            "artifact_id": f"artifact-{name}",
            "paths": [path.relative_to(tmp_path).as_posix()],
        }
    component_manifest = _write_yaml(
        tmp_path / "instrument-components.yaml",
        {
            "instrument_component_manifest": {
                "version": "0.1.0",
                "hash_method": "path_bound_sha256_manifest_v1",
            },
            "components": components,
        },
    )

    roster = _write_yaml(
        tmp_path / "roster.yaml",
        {
            "schema_version": "0.1.0",
            "members": [
                {
                    "member_id": "R-INT",
                    "roles": ["primary_reviewer_interoperability"],
                },
                {
                    "member_id": "R-CLIN",
                    "roles": ["primary_reviewer_clinical_informatics"],
                },
                {"member_id": "R-ADJ", "roles": ["adjudicator"]},
                {"member_id": "R-DATA", "roles": ["data_custodian"]},
            ],
        },
    )
    assignments = _write_yaml(
        tmp_path / "assignments.yaml",
        {"schema_version": "0.1.0"},
    )
    primary_hypothesis = _write_yaml(
        tmp_path / "primary-hypothesis.yaml",
        {"schema_version": "0.1.0"},
    )
    analysis = _write_yaml(
        tmp_path / "analysis.yaml",
        {"schema_version": "0.1.0"},
    )
    sample = _write_yaml(
        tmp_path / "sample.yaml",
        {"schema_version": "0.1.0"},
    )
    model = _write_yaml(
        tmp_path / "model.yaml",
        {"schema_version": "0.6.0"},
    )
    pilot = _write_yaml(
        tmp_path / "pilot.yaml",
        {
            "schema_version": "0.4.0",
            "acceptance_gate": {
                "minimum_sensitivity": 0.8,
                "sensitivity_statistic": "lower_95_percent_confidence_bound",
                "minimum_ppv": 0.8,
                "ppv_statistic": "lower_95_percent_confidence_bound",
                "maximum_runtime_indeterminate_rate": 0.1,
                "indeterminate_statistic": "upper_95_percent_confidence_bound",
            },
        },
    )
    case_manifest = tmp_path / "sealed-case-manifest.json"
    case_manifest.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "manifest_id": "SEALED-CASES-001",
                "status": "sealed",
                "created_at": "2026-10-20T22:00:00Z",
                "split": "sealed_test",
                "case_count": 2,
                "cases": [
                    {
                        "case_id": "CASE-001",
                        "scenario_family": "LAB-001",
                        "analysis_cluster_id": "CLUSTER-001",
                        "source_input_sha256": "a" * 64,
                        "canonical_graph_sha256": "b" * 64,
                    },
                    {
                        "case_id": "CASE-002",
                        "scenario_family": "LAB-006",
                        "analysis_cluster_id": "CLUSTER-002",
                        "source_input_sha256": "c" * 64,
                        "canonical_graph_sha256": "d" * 64,
                    },
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sealed_bundle = tmp_path / "sealed-bundle.bin"
    sealed_bundle.write_bytes(b"sealed synthetic bundle bytes")

    return {
        "tooling": tooling_path,
        "components": component_manifest,
        "roster": roster,
        "assignments": assignments,
        "primary_hypothesis": primary_hypothesis,
        "analysis": analysis,
        "sample": sample,
        "model": model,
        "pilot": pilot,
        "case_manifest": case_manifest,
        "sealed_bundle": sealed_bundle,
    }


def _patch_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        _MODULE,
        "_validate_governance_crosslinks",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_freeze_readiness",
        lambda _: SimpleNamespace(ready=True, manifest_status="frozen"),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_reviewer_roster",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_case_assignment_manifest",
        lambda *_args, **_kwargs: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_primary_vur_hypothesis",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_analysis_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_sample_size_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_model_prompt_freeze",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )
    monkeypatch.setattr(
        _MODULE,
        "assess_pilot_acceptance_preregistration",
        lambda _: SimpleNamespace(ready=True, blockers=()),
    )


def _build(tmp_path: Path, paths: dict[str, Path]) -> dict:
    return _MODULE.build_freeze_manifest(
        tooling_manifest_path=paths["tooling"],
        instrument_component_manifest_path=paths["components"],
        reviewer_roster_path=paths["roster"],
        case_assignment_path=paths["assignments"],
        primary_vur_hypothesis_path=paths["primary_hypothesis"],
        analysis_preregistration_path=paths["analysis"],
        sample_size_path=paths["sample"],
        model_config_path=paths["model"],
        pilot_acceptance_path=paths["pilot"],
        sealed_bundle_path=paths["sealed_bundle"],
        sealed_case_manifest_path=paths["case_manifest"],
        manifest_id="FREEZE-001",
        freeze_timestamp="2026-10-20T23:00:00Z",
        protocol_version="1.0",
        repository_commit="abcdef1",
        bundle_id="SEALED-001",
        repository_root=tmp_path,
    )


def test_freeze_manifest_builder_binds_all_components_and_governance_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _fixture(tmp_path)
    _patch_ready(monkeypatch)

    result = _build(tmp_path, paths)

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    assert result["schema_version"] == "0.8.0"
    assert result["freeze_complete"] is True
    assert set(result["instrument_components"]) == set(_COMPONENT_NAMES)
    assert result["sealed_set"]["case_count"] == 2
    assert result["sealed_set"]["opened"] is False
    assert {
        item["purpose"] for item in result["dependencies"]
    } >= {"terminology", "ucum", "fhir_validation", "hl7v2_validation"}
    assert result["acceptance_gate"]["defined_before_sealed_opening"] is True
    assert result["primary_vur_hypothesis"]["artifact_id"] == (
        "primary-vur-hypothesis-preregistration"
    )


def test_freeze_manifest_builder_component_hash_changes_with_component_bytes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _fixture(tmp_path)
    _patch_ready(monkeypatch)
    first = _build(tmp_path, paths)

    component = tmp_path / "components/verifier.txt"
    component.write_text("changed verifier bytes\n", encoding="utf-8")
    second = _build(tmp_path, paths)

    assert first["instrument_components"]["verifier"]["sha256"] != second[
        "instrument_components"
    ]["verifier"]["sha256"]


def test_freeze_manifest_builder_refuses_unfrozen_tooling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _fixture(tmp_path)
    _patch_ready(monkeypatch)
    monkeypatch.setattr(
        _MODULE,
        "assess_freeze_readiness",
        lambda _: SimpleNamespace(ready=False, manifest_status="candidate"),
    )

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "tooling manifest is not confirmatory-frozen" in str(exc)
    else:
        raise AssertionError("unfrozen tooling must block final freeze assembly")


def test_freeze_manifest_builder_refuses_unready_governance_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _fixture(tmp_path)
    _patch_ready(monkeypatch)
    monkeypatch.setattr(
        _MODULE,
        "assess_model_prompt_freeze",
        lambda _: SimpleNamespace(
            ready=False,
            blockers=("model snapshot missing",),
        ),
    )

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "model snapshot missing" in str(exc)
    else:
        raise AssertionError("unready model freeze must block final freeze")


def test_freeze_manifest_builder_refuses_unready_primary_hypothesis(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _fixture(tmp_path)
    _patch_ready(monkeypatch)
    monkeypatch.setattr(
        _MODULE,
        "assess_primary_vur_hypothesis",
        lambda _: SimpleNamespace(
            ready=False,
            blockers=("primary threshold not frozen",),
        ),
    )

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "primary threshold not frozen" in str(exc)
    else:
        raise AssertionError(
            "unready primary VUR hypothesis must block final freeze"
        )


def _crosslink_documents() -> tuple[dict, dict, dict, dict]:
    primary = {
        "record_id": "PRIMARY-VUR-001",
        "hypothesis": {"nontrivial_vur_threshold": 0.10},
        "target_population": {
            "model_strategy_aggregation_policy": "Frozen aggregation.",
            "cluster_id_field": "analysis_cluster_id",
        },
        "inference": {
            "method": "cluster_aware_one_sided_threshold_test",
            "alpha": 0.05,
            "sidedness": "one_sided",
            "decision_rule": "Frozen decision rule.",
        },
    }
    sample = {
        "model_keys": ["M1"],
        "frozen_method": {
            "model_prompt_configuration_sha256": "c" * 64,
        },
    }
    model = {"llm_models": [{"model_key": "M1"}]}
    analysis = {
        "frozen_inputs": {
            "repository_commit": "abcdef1",
            "primary_vur_hypothesis_sha256": "a" * 64,
            "sample_size_preregistration_sha256": "b" * 64,
            "model_prompt_configuration_sha256": "c" * 64,
        },
        "primary_hypothesis": {
            "record_id": "PRIMARY-VUR-001",
            "nontrivial_vur_threshold": 0.10,
            "model_strategy_aggregation_policy": "Frozen aggregation.",
            "inference_method": "cluster_aware_one_sided_threshold_test",
            "alpha": 0.05,
            "sidedness": "one_sided",
            "cluster_id_field": "analysis_cluster_id",
            "decision_rule": "Frozen decision rule.",
        },
    }
    return analysis, primary, sample, model


def test_governance_crosslinks_accept_matching_frozen_records() -> None:
    analysis, primary, sample, model = _crosslink_documents()

    _MODULE._validate_governance_crosslinks(
        analysis=analysis,
        primary_hypothesis=primary,
        sample_size=sample,
        model_config=model,
        repository_commit="abcdef1",
        primary_hypothesis_sha256="a" * 64,
        sample_size_sha256="b" * 64,
        model_config_sha256="c" * 64,
    )


def test_governance_crosslinks_reject_analysis_hash_drift() -> None:
    analysis, primary, sample, model = _crosslink_documents()
    analysis["frozen_inputs"]["sample_size_preregistration_sha256"] = "d" * 64

    try:
        _MODULE._validate_governance_crosslinks(
            analysis=analysis,
            primary_hypothesis=primary,
            sample_size=sample,
            model_config=model,
            repository_commit="abcdef1",
            primary_hypothesis_sha256="a" * 64,
            sample_size_sha256="b" * 64,
            model_config_sha256="c" * 64,
        )
    except ValueError as exc:
        assert "sample-size preregistration hash" in str(exc)
    else:
        raise AssertionError("stale sample-size hash must be rejected")


def test_governance_crosslinks_reject_repository_commit_drift() -> None:
    analysis, primary, sample, model = _crosslink_documents()

    try:
        _MODULE._validate_governance_crosslinks(
            analysis=analysis,
            primary_hypothesis=primary,
            sample_size=sample,
            model_config=model,
            repository_commit="deadbee",
            primary_hypothesis_sha256="a" * 64,
            sample_size_sha256="b" * 64,
            model_config_sha256="c" * 64,
        )
    except ValueError as exc:
        assert "repository_commit" in str(exc)
    else:
        raise AssertionError("repository commit drift must be rejected")


def test_governance_crosslinks_reject_model_key_drift() -> None:
    analysis, primary, sample, model = _crosslink_documents()
    sample["model_keys"] = ["M2"]

    try:
        _MODULE._validate_governance_crosslinks(
            analysis=analysis,
            primary_hypothesis=primary,
            sample_size=sample,
            model_config=model,
            repository_commit="abcdef1",
            primary_hypothesis_sha256="a" * 64,
            sample_size_sha256="b" * 64,
            model_config_sha256="c" * 64,
        )
    except ValueError as exc:
        assert "model_keys do not match" in str(exc)
    else:
        raise AssertionError("model-key drift must be rejected")


def test_governance_crosslinks_reject_threshold_summary_drift() -> None:
    analysis, primary, sample, model = _crosslink_documents()
    analysis["primary_hypothesis"]["nontrivial_vur_threshold"] = 0.20

    try:
        _MODULE._validate_governance_crosslinks(
            analysis=analysis,
            primary_hypothesis=primary,
            sample_size=sample,
            model_config=model,
            repository_commit="abcdef1",
            primary_hypothesis_sha256="a" * 64,
            sample_size_sha256="b" * 64,
            model_config_sha256="c" * 64,
        )
    except ValueError as exc:
        assert "nontrivial_vur_threshold" in str(exc)
    else:
        raise AssertionError("threshold summary drift must be rejected")
