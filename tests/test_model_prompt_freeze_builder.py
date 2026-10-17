import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import jsonschema
import yaml

from fhirbridge.artifact_bundle import hash_artifact_bundle

_MODULE_PATH = Path("models/build_model_prompt_freeze.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_model_prompt_freeze",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_MODEL_SCHEMA = Path("models/schema/model_prompt_freeze.schema.json")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_yaml(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> dict[str, Path]:
    execution = _write(
        tmp_path / "models/execution_policy.yaml",
        _MODULE._DEFAULT_EXECUTION_POLICY.read_text(encoding="utf-8"),
    )
    direct = _write(
        tmp_path / "models/prompts/direct.txt",
        "direct prompt\n",
    )
    mapping = _write(
        tmp_path / "models/prompts/mapping.txt",
        "mapping prompt\n",
    )
    strategy = _write(
        tmp_path / "src/fhirbridge/model_strategies.py",
        "# strategy implementation\n",
    )
    repair = _write(
        tmp_path / "src/fhirbridge/syntax_repair.py",
        "# repair implementation\n",
    )
    contract = _write(
        tmp_path / "contracts/contract.yaml",
        "contract:\n  id: F2V-LAB-ORU-R01-001\n  version: 0.3.0\n",
    )

    renderer_files = [
        _write(tmp_path / f"src/fhirbridge/renderers/{name}", f"# {name}\n")
        for name in ("__init__.py", "base.py", "fhir_r4_a.py", "hl7v251_oru_a.py")
    ]
    relative_renderer_paths = [
        path.relative_to(tmp_path).as_posix() for path in renderer_files
    ]
    component_manifest = _write_yaml(
        tmp_path / "benchmark/instrument_component_manifest.yaml",
        {
            "instrument_component_manifest": {
                "hash_method": "path_bound_sha256_manifest_v1",
            },
            "components": {
                "deterministic_baseline_renderer": {
                    "artifact_id": (
                        "deterministic-fhir-to-hl7v2-baseline-renderer"
                    ),
                    "paths": relative_renderer_paths,
                }
            },
        },
    )
    baseline_digest = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="deterministic-fhir-to-hl7v2-baseline-renderer",
        relative_paths=relative_renderer_paths,
    ).sha256

    mapping_context = _write(
        tmp_path / "models/generated/frozen_mapping_context.json",
        '{"context_id":"TEST"}\n',
    )
    mapping_manifest = _write(
        tmp_path / "models/generated/frozen_mapping_context_manifest.json",
        json.dumps({"sha256": _sha(mapping_context)}) + "\n",
    )

    baseline = {
        "schema_version": "0.1.0",
        "qualification_id": "BASELINE-QUAL-001",
        "status": "qualified",
        "created_at": "2026-10-20T20:00:00Z",
        "repository_commit": "abcdef1",
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.3.0",
            "sha256": _sha(contract),
            "freeze_status": "frozen",
        },
        "target_profile": {
            "name": "LRI_NG_FRU_Profile_V3",
            "edition": "5",
            "errata": "2024DEC",
            "profile_bundle_sha256": "2" * 64,
            "qualification_report_sha256": "3" * 64,
        },
        "renderer_component": {
            "component_name": "deterministic_baseline_renderer",
            "artifact_id": "deterministic-fhir-to-hl7v2-baseline-renderer",
            "sha256": baseline_digest,
        },
        "primary_family_evidence": [
            {
                "template_id": f"LAB-{index:03d}",
                "order_context_present": True,
                "structural_validity": "VALID",
                "semantic_verdict": "FAITHFUL",
                "validation_record_sha256": f"{index:x}" * 64,
            }
            for index in range(1, 12)
        ],
        "aggregate": {
            "primary_family_count": 11,
            "all_primary_families_structurally_valid": True,
            "all_primary_families_semantically_faithful": True,
            "order_context_supported": True,
            "exact_profile_validation_used": True,
        },
        "attestation": {
            "no_invented_business_facts": True,
            "development_placeholder_codes_absent": True,
            "same_frozen_instrument_used_for_all_families": True,
            "confirmatory_model_outputs_not_used": True,
        },
    }
    baseline_path = _write_yaml(
        tmp_path / "models/baseline_qualification.yaml",
        baseline,
    )

    models_path = _write_yaml(
        tmp_path / "models/model_declarations.yaml",
        {
            "schema_version": "0.1.0",
            "models": [
                {
                    "model_key": "M1",
                    "provider": "provider-x",
                    "model_id": "model-x",
                    "model_revision_or_snapshot": "snapshot-2026-10",
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "max_output_tokens": 4096,
                    "seed_policy": "fixed_supported_seed",
                    "seed": 20261020,
                    "structured_output_mode": "plain_text_hl7_message",
                }
            ],
        },
    )

    return {
        "execution": execution,
        "direct": direct,
        "mapping": mapping,
        "strategy": strategy,
        "repair": repair,
        "contract": contract,
        "component_manifest": component_manifest,
        "mapping_context": mapping_context,
        "mapping_manifest": mapping_manifest,
        "baseline": baseline_path,
        "models": models_path,
    }


def _build(tmp_path: Path, paths: dict[str, Path]) -> dict:
    return _MODULE.build_model_prompt_freeze(
        model_declarations_path=paths["models"],
        baseline_qualification_path=paths["baseline"],
        mapping_context_path=paths["mapping_context"],
        mapping_context_manifest_path=paths["mapping_manifest"],
        instrument_component_manifest_path=paths["component_manifest"],
        config_id="MODEL-FREEZE-001",
        created_at="2026-10-20T21:00:00Z",
        repository_root=tmp_path,
        execution_policy_path=paths["execution"],
        direct_prompt_path=paths["direct"],
        mapping_prompt_path=paths["mapping"],
        strategy_implementation_path=paths["strategy"],
        syntax_repair_path=paths["repair"],
        contract_path=paths["contract"],
    )


def test_model_freeze_builder_produces_schema_valid_ready_configuration(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    result = _build(tmp_path, paths)

    schema = json.loads(_MODEL_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    assert result["schema_version"] == "0.6.0"
    assert result["status"] == "frozen"
    assert result["deterministic_baseline"]["implementation_artifact"][
        "path_or_ref"
    ] == "component://deterministic_baseline_renderer"
    mapping = next(
        item
        for item in result["llm_strategies"]
        if item["strategy_id"] == "mapping_aware_llm"
    )
    repair = next(
        item
        for item in result["llm_strategies"]
        if item["strategy_id"] == "mapping_aware_plus_syntax_repair"
    )
    assert mapping["prompt_artifacts"] == repair["prompt_artifacts"]
    assert mapping["mapping_context_artifacts"] == repair[
        "mapping_context_artifacts"
    ]


def test_model_freeze_builder_rejects_stale_baseline_renderer_digest(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    document = yaml.safe_load(paths["baseline"].read_text(encoding="utf-8"))
    document["renderer_component"]["sha256"] = "f" * 64
    _write_yaml(paths["baseline"], document)

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "renderer digest does not match" in str(exc)
    else:
        raise AssertionError("stale baseline renderer digest must fail")


def test_model_freeze_builder_rejects_stale_mapping_context_manifest(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    paths["mapping_manifest"].write_text(
        json.dumps({"sha256": "f" * 64}) + "\n",
        encoding="utf-8",
    )

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "mapping-context manifest hash does not match" in str(exc)
    else:
        raise AssertionError("stale mapping context hash must fail")


def test_model_freeze_builder_rejects_placeholder_provider_declaration(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    declarations = yaml.safe_load(paths["models"].read_text(encoding="utf-8"))
    declarations["models"][0]["provider"] = "TO_BE_FROZEN"
    _write_yaml(paths["models"], declarations)

    try:
        _build(tmp_path, paths)
    except ValueError as exc:
        assert "provider is missing or placeholder" in str(exc)
    else:
        raise AssertionError("placeholder provider declaration must fail")
