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
    for line in reversed(stdout.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and "error_total" in value:
                return value
    raise ValueError("NIST validator JSON report was not found in process output")


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

    controls: list[tuple[str, Path]] = []
    for control in build_structural_negative_controls(rendered.artifact):
        path = output_dir / f"{control.control_id}.er7"
        path.write_text(control.artifact, encoding="utf-8")
        controls.append((control.control_id, path))
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
    for control_id, path in controls:
        report = _run_validator(profile_dir, path)
        negative_reports.append(
            {
                "control_id": control_id,
                "path": str(path),
                "report": report,
                "passed_expected_failure": int(report.get("error_total", 0)) > 0,
            }
        )

    baseline_passed = int(baseline_report.get("error_total", 0)) == 0
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
