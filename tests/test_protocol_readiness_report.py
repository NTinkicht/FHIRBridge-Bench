import importlib.util
from pathlib import Path

import yaml

_MODULE_PATH = Path("qualification/freeze/report_protocol_readiness.py")
_SPEC = importlib.util.spec_from_file_location(
    "report_protocol_readiness",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_protocol_readiness_reports_cross_file_consistency() -> None:
    report = _MODULE.build_report()

    assert report["implementation_consistency"]["ready"] is True
    assert report["implementation_consistency"]["blocker_count"] == 0
    assert report["implementation_consistency"]["blockers"] == []
    assert report["measurement_policy"]["consistent"] is True
    assert report["measurement_policy"]["freeze_ready"] is False
    assert report["measurement_policy"]["consistency_blockers"] == []
    assert report["measurement_policy"]["freeze_blockers"]


def test_protocol_readiness_fails_closed_on_execution_policy_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    policy = yaml.safe_load(
        Path("models/execution_policy.yaml").read_text(encoding="utf-8")
    )
    policy["generation_attempt"]["provider_generation_calls_per_case_model"][
        "mapping_aware_plus_syntax_repair"
    ] = 1
    mutated = tmp_path / "execution-policy.yaml"
    mutated.write_text(
        yaml.safe_dump(policy, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(_MODULE, "_EXECUTION_POLICY", mutated)

    report = _MODULE.build_report()

    assert report["implementation_consistency"]["ready"] is False
    assert report["implementation_consistency"]["blocker_count"] >= 1
    assert any(
        "provider call counts drift" in item
        for item in report["implementation_consistency"]["blockers"]
    )
    assert report["ready_for_confirmatory_inference"] is False


def test_protocol_readiness_reports_measurement_policy_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    severity = yaml.safe_load(
        Path("benchmark/severity_policy_candidate.yaml").read_text(
            encoding="utf-8"
        )
    )
    severity["primary_endpoint_major_candidate"]["levels"] = ["S1", "S2", "S3"]
    mutated = tmp_path / "severity-policy.yaml"
    mutated.write_text(
        yaml.safe_dump(severity, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(_MODULE, "_SEVERITY_POLICY", mutated)

    report = _MODULE.build_report()

    assert report["measurement_policy"]["consistent"] is False
    assert any(
        "major endpoint candidate" in item
        for item in report["measurement_policy"]["consistency_blockers"]
    )
    assert report["ready_for_confirmatory_inference"] is False
