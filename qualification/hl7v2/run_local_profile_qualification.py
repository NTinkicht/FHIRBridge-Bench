"""Run local HL7 v2.5.1 LRI profile qualification against frozen fixtures."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from fhirbridge.hl7v2_profile_bundle import assert_single_oru_r01_profile
from fhirbridge.hl7v2_profile_pin import assert_profile_bundle_matches_pin
from fhirbridge.hl7v2_negative_controls import build_structural_negative_controls
from fhirbridge.renderers import Hl7V251OruRendererA
from fhirbridge.schema_validation import load_yaml
from fhirbridge.canonical import generate_lab_scenario

_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml")
_PROFILE_PIN = Path("benchmark/hl7v2_lri_profile_pin.yaml")
_HARNESS_POM = Path("qualification/hl7v2/pom.xml")
_VENDOR = Path("vendor/lib-hl7v2-nist-validator")
_MAIN_CLASS = "org.fhirbridge.hl7v2.ValidateLriProfile"


def _extract_json(stdout: str) -> dict:
    summary: dict | None = None
    full_report: dict | None = None
    for line in reversed(stdout.splitlines()):
        candidate = line.strip()
        if not (candidate.startswith("{") and candidate.endswith("}")):
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        if summary is None and "error_total" in value:
            summary = value
        elif full_report is None and "entries" in value:
            full_report = value
        if summary is not None and full_report is not None:
            break

    if summary is None:
        raise ValueError("NIST validator JSON summary was not found in process output")
    if full_report is None:
        raise ValueError("NIST validator entry-level JSON report was not found in process output")

    result = dict(summary)
    result["entries"] = full_report.get("entries", {})
    result["reported_counts"] = {
        key: full_report.get(key)
        for key in (
            "error-count",
            "warning-count",
            "alert-count",
            "informational-count",
        )
        if key in full_report
    }
    return result


def _error_entries(report: dict) -> list[dict]:
    entries = report.get("entries", {})
    if not isinstance(entries, dict):
        return []
    result: list[dict] = []
    for bucket in ("structure", "value-set", "content"):
        values = entries.get(bucket, [])
        if not isinstance(values, list):
            continue
        for entry in values:
            if (
                isinstance(entry, dict)
                and str(entry.get("classification", "")).lower() == "error"
            ):
                result.append(entry)
    return result


def _expected_error_observed(
    report: dict,
    expected_tokens: tuple[str, ...],
) -> bool:
    if not expected_tokens:
        return False
    lowered_tokens = tuple(token.lower() for token in expected_tokens)
    for entry in _error_entries(report):
        haystack = " ".join(
            str(entry.get(key, ""))
            for key in ("path", "description", "category")
        ).lower()
        if all(token in haystack for token in lowered_tokens):
            return True
    return False


def _blocking_total(report: dict) -> int:
    """Fail closed on errors, warnings, and alerts before an allowlist is frozen."""

    return sum(
        int(report.get(key, 0))
        for key in ("error_total", "warning_total", "alert_total")
    )


def _run_validator(profile_dir: Path, message_path: Path) -> dict:
    args = (
        f"{profile_dir.resolve()} {message_path.resolve()} --report-only"
    )
    command = [
        "mvn",
        "-q",
        "-f",
        str(_HARNESS_POM),
        "exec:java",
        f"-Dexec.mainClass={_MAIN_CLASS}",
        f"-Dexec.args={args}",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0:
        raise RuntimeError(
            "NIST validator harness failed to execute:\n" + combined[-8000:]
        )
    return _extract_json(combined)


def _render_fixtures(output_dir: Path) -> tuple[Path, list[tuple[str, Path]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = generate_lab_scenario("LAB-001", 9501)
    contract = load_yaml(_CONTRACT)
    rendered = Hl7V251OruRendererA().render(graph, contract=contract)

    baseline = output_dir / "baseline-LAB-001-9501.er7"
    baseline.write_text(rendered.artifact, encoding="utf-8")

    controls: list[tuple[str, Path, tuple[str, ...]]] = []
    for control in build_structural_negative_controls(rendered.artifact):
        path = output_dir / f"{control.control_id}.er7"
        path.write_text(control.artifact, encoding="utf-8")
        controls.append(
            (
                control.control_id,
                path,
                control.expected_error_location_tokens,
            )
        )
    return baseline, controls


def _verify_local_prerequisites(profile_dir: Path) -> None:
    if not profile_dir.is_dir():
        raise ValueError(f"profile directory does not exist: {profile_dir}")
    assert_single_oru_r01_profile(profile_dir)
    if not _PROFILE_PIN.is_file():
        raise ValueError(f"profile pin is missing: {_PROFILE_PIN}")
    pin = load_yaml(_PROFILE_PIN)
    assert_profile_bundle_matches_pin(profile_dir, pin)
    if not _HARNESS_POM.is_file():
        raise ValueError(f"qualification harness POM is missing: {_HARNESS_POM}")
    if not (_VENDOR / "pom.xml").is_file():
        raise ValueError(
            "pinned CDC validator checkout is missing. Clone "
            "CDCgov/lib-hl7v2-nist-validator at the frozen commit into "
            "vendor/lib-hl7v2-nist-validator before running local qualification."
        )


def _compile_harness() -> None:
    completed = subprocess.run(
        ["mvn", "-q", "-f", str(_HARNESS_POM), "compile"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "HL7 v2 qualification harness did not compile:\n"
            + completed.stdout[-4000:]
            + "\n"
            + completed.stderr[-4000:]
        )


def qualify_profile(profile_dir: Path, output_dir: Path) -> dict:
    """Qualify one exact local profile bundle against baseline and negatives."""

    _verify_local_prerequisites(profile_dir)
    _compile_harness()
    baseline_path, controls = _render_fixtures(output_dir)

    baseline_report = _run_validator(profile_dir, baseline_path)
    negative_reports = []
    for control_id, path, expected_tokens in controls:
        report = _run_validator(profile_dir, path)
        expected_location_observed = _expected_error_observed(
            report,
            expected_tokens,
        )
        negative_reports.append(
            {
                "control_id": control_id,
                "path": str(path),
                "expected_error_location_tokens": list(expected_tokens),
                "report": report,
                "expected_location_observed": expected_location_observed,
                "passed_expected_failure": (
                    int(report.get("error_total", 0)) > 0
                    and expected_location_observed
                ),
            }
        )

    baseline_passed = _blocking_total(baseline_report) == 0
    negative_controls_passed = all(
        item["passed_expected_failure"] for item in negative_reports
    )
    return {
        "profile_directory": str(profile_dir.resolve()),
        "baseline": {
            "path": str(baseline_path),
            "report": baseline_report,
            "passed": baseline_passed,
        },
        "negative_controls": negative_reports,
        "local_reference_messages_passed": baseline_passed,
        "structural_negative_controls_passed": negative_controls_passed,
        "warning_alert_policy": (
            "fail_closed_on_all_warning_and_alert_classifications_until_"
            "explicit_allowlist_is_frozen"
        ),
        "negative_control_policy": (
            "requires_error_at_expected_semantic_locus_not_merely_any_error"
        ),
        "qualification_passed": baseline_passed and negative_controls_passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_directory", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("qualification/hl7v2/results/local-profile"),
    )
    args = parser.parse_args()

    report = qualify_profile(args.profile_directory, args.output_directory)
    output = args.output_directory / "qualification-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["qualification_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
