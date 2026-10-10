import importlib.util
import json
from pathlib import Path

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
