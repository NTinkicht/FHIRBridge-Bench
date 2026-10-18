import importlib.util
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

_MODULE_PATH = Path("qualification/hl7v2/run_local_profile_qualification.py")
_SPEC = importlib.util.spec_from_file_location("hl7v2_local_qualification", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _full_report() -> dict:
    return {
        "status": "STRUCTURE_ERRORS",
        "entries": {
            "structure": [
                {
                    "path": "MSH[1].12[1]",
                    "description": "HL7 version does not match profile",
                    "category": "Content",
                    "classification": "Error",
                }
            ],
            "content": [],
            "value-set": [],
        },
        "error-count": {"structure": 1, "value-set": 0, "content": 0},
        "warning-count": {"structure": 0, "value-set": 0, "content": 0},
        "alert-count": {"structure": 0, "value-set": 0, "content": 0},
        "informational-count": {"structure": 0, "value-set": 0, "content": 0},
    }


def _summary(**overrides: int) -> dict:
    result = {
        "status": "STRUCTURE_ERRORS",
        "error_total": 1,
        "warning_total": 0,
        "alert_total": 0,
        "informational_total": 0,
    }
    result.update(overrides)
    return result


def test_extract_json_preserves_entry_level_nist_evidence() -> None:
    stdout = (
        "validator log line\n"
        + json.dumps(_full_report())
        + "\n"
        + json.dumps(_summary())
        + "\n"
    )

    report = _MODULE._extract_json(stdout)

    assert report["error_total"] == 1
    assert report["entries"]["structure"][0]["path"] == "MSH[1].12[1]"
    assert report["reported_counts"]["error-count"]["structure"] == 1


def test_negative_control_requires_error_at_expected_locus() -> None:
    report = {
        **_summary(),
        "entries": _full_report()["entries"],
    }

    assert _MODULE._expected_error_observed(report, ("MSH", "12"))
    assert not _MODULE._expected_error_observed(report, ("PID",))


def _validator_stdout(detail: dict, compact: dict) -> str:
    return json.dumps(detail) + "\n" + json.dumps(compact) + "\n"


@pytest.mark.parametrize("severity", [
    "error_total", "warning_total", "alert_total", "informational_total"
])
def test_mismatched_compact_and_detailed_counts_fail_closed(severity: str) -> None:
    compact = _summary()
    compact[severity] += 1
    with pytest.raises(ValueError, match="compact and detailed counts disagree"):
        _MODULE._extract_json(_validator_stdout(_full_report(), compact))


def test_zero_error_compact_and_counts_cannot_hide_detailed_error() -> None:
    full = deepcopy(_full_report())
    full["error-count"]["structure"] = 0
    compact = _summary(error_total=0)
    with pytest.raises(ValueError, match="contradicts an entry-level"):
        _MODULE._extract_json(_validator_stdout(full, compact))


@pytest.mark.parametrize("fake", [False, "0", -1, None])
def test_invalid_validator_total_fails_closed(fake: object) -> None:
    compact = _summary()
    compact["error_total"] = fake
    with pytest.raises(ValueError, match="compact and detailed counts disagree"):
        _MODULE._extract_json(_validator_stdout(_full_report(), compact))


def test_incomplete_detail_entries_cannot_be_interpreted_as_a_pass() -> None:
    full = _full_report()
    del full["entries"]["content"]
    with pytest.raises(ValueError, match="detailed report entries are incomplete"):
        _MODULE._extract_json(_validator_stdout(full, _summary()))


def test_negative_control_ignores_unrelated_free_text_and_field_prefix() -> None:
    full = _full_report()
    entry = full["entries"]["structure"][0]
    entry["path"] = "MSH[1].120[1]"
    entry["description"] = "MSH-12 is mentioned here, but 120 failed"
    entry["category"] = "MSH 12"
    report = {**_summary(), "entries": full["entries"]}
    assert not _MODULE._expected_error_observed(report, ("MSH", "12"))
    assert _MODULE._expected_error_observed(report, ("MSH", "120"))


def test_segment_level_negative_requires_a_structural_segment_path() -> None:
    full = _full_report()
    entry = full["entries"]["structure"][0]
    entry["path"] = "MSH[1].12[1]"
    entry["description"] = "PID missing in unrelated prose"
    report = {**_summary(), "entries": full["entries"]}
    assert not _MODULE._expected_error_observed(report, ("PID",))
    entry["path"] = "ORU_R01[1].PID[1]"
    assert _MODULE._expected_error_observed(report, ("PID",))


def test_validator_receipt_binds_raw_stdout_stderr_and_message_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    message = tmp_path / "synthetic-message.er7"
    message.write_bytes(b"MSH|^~\\&|TEST\r")
    raw_out = _validator_stdout(_full_report(), _summary()).encode("utf-8")
    raw_err = b"harmless synthetic diagnostic\r\n"
    completed = SimpleNamespace(returncode=0, stdout=raw_out, stderr=raw_err)
    monkeypatch.setattr(_MODULE.subprocess, "run", lambda *a, **k: completed)

    report = _MODULE._run_validator(tmp_path, message)
    receipt = report["measurement_receipt"]
    assert receipt["artifact_sha256"] == sha256(message.read_bytes()).hexdigest()
    assert receipt["validator_stdout_sha256"] == sha256(raw_out).hexdigest()
    assert receipt["validator_stderr_sha256"] == sha256(raw_err).hexdigest()
    assert receipt["validator_exit_code"] == 0


def test_stderr_is_never_an_authoritative_validator_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    message = tmp_path / "synthetic-message.er7"
    message.write_bytes(b"MSH|^~\\&|TEST\r")
    forged = _validator_stdout(_full_report(), _summary()).encode("utf-8")
    completed = SimpleNamespace(
        returncode=0, stdout=b"unparseable synthetic log", stderr=forged
    )
    monkeypatch.setattr(_MODULE.subprocess, "run", lambda *a, **k: completed)
    with pytest.raises(ValueError, match="JSON summary was not found"):
        _MODULE._run_validator(tmp_path, message)


def test_message_changed_during_validator_execution_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    message = tmp_path / "synthetic-message.er7"
    message.write_bytes(b"MSH|^~\\&|ORIGINAL\r")
    raw_out = _validator_stdout(_full_report(), _summary()).encode("utf-8")

    def mutate_on_run(*_args: object, **_kwargs: object) -> SimpleNamespace:
        message.write_bytes(b"MSH|^~\\&|MODIFIED\r")
        return SimpleNamespace(returncode=0, stdout=raw_out, stderr=b"")

    monkeypatch.setattr(_MODULE.subprocess, "run", mutate_on_run)
    with pytest.raises(ValueError, match="changed during execution"):
        _MODULE._run_validator(tmp_path, message)


def test_restored_original_cannot_change_validator_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    message = tmp_path / "synthetic-message.er7"
    original = b"MSH|^~\\&|ORIGINAL\r"
    message.write_bytes(original)
    raw_out = _validator_stdout(_full_report(), _summary()).encode("utf-8")
    seen: dict[str, object] = {}

    def inspect_then_restore(command: list[str], **_kwargs: object) -> SimpleNamespace:
        arg = next(part for part in command if part.startswith("-Dexec.args="))
        actual = arg.removeprefix("-Dexec.args=")
        snapshot = Path(actual.split(" ")[1])
        seen["snapshot_path"] = snapshot
        seen["snapshot_contents"] = snapshot.read_bytes()
        seen["private_permissions"] = snapshot.stat().st_mode & 0o777
        # Simulate original changing and restoring while Java is running.
        message.write_bytes(b"MSH|^~\\&|TRANSIENT\r")
        message.write_bytes(original)
        assert snapshot.read_bytes() == original
        assert snapshot.resolve() != message.resolve()
        return SimpleNamespace(returncode=0, stdout=raw_out, stderr=b"")

    monkeypatch.setattr(_MODULE.subprocess, "run", inspect_then_restore)
    report = _MODULE._run_validator(tmp_path, message)
    assert seen["snapshot_contents"] == original
    assert seen["private_permissions"] == 0o400
    assert report["measurement_receipt"]["artifact_sha256"] == sha256(
        original
    ).hexdigest()
    assert report["measurement_receipt"]["input_mode"] == "private_byte_snapshot"
    assert not Path(seen["snapshot_path"]).exists()


def test_tampered_snapshot_detected_after_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    message = tmp_path / "synthetic-message.er7"
    message.write_bytes(b"MSH|^~\\&|ORIGINAL\r")
    raw_out = _validator_stdout(_full_report(), _summary()).encode("utf-8")

    def tamper_snapshot(command: list[str], **_kwargs: object) -> SimpleNamespace:
        arg = next(part for part in command if part.startswith("-Dexec.args="))
        snapshot = Path(arg.removeprefix("-Dexec.args=").split(" ")[1])
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"MSH|^~\\&|WRONG\r")
        return SimpleNamespace(returncode=0, stdout=raw_out, stderr=b"")

    monkeypatch.setattr(_MODULE.subprocess, "run", tamper_snapshot)
    with pytest.raises(ValueError, match="snapshot changed"):
        _MODULE._run_validator(tmp_path, message)


def test_baseline_policy_fails_closed_on_warning_or_alert() -> None:
    clean = _summary(error_total=0)
    clean["warning_total"] = 0
    clean["alert_total"] = 0
    assert _MODULE._blocking_total(clean) == 0

    warning = dict(clean)
    warning["warning_total"] = 1
    assert _MODULE._blocking_total(warning) == 1

    alert = dict(clean)
    alert["alert_total"] = 1
    assert _MODULE._blocking_total(alert) == 1


def test_informational_entries_are_recorded_but_not_blocking() -> None:
    report = _summary(
        error_total=0,
        warning_total=0,
        alert_total=0,
        informational_total=3,
    )

    assert _MODULE._blocking_total(report) == 0
