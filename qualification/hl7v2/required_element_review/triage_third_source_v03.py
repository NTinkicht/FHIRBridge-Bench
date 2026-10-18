"""Private offline v0.3 triple-census triage; does not qualify HL7 rules."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from fhirbridge.lri_lock_json import load_coordinator_lock_json
from fhirbridge.path_b_v03_source_census import audit_v03_independent_source_census

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _private(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(_REPO_ROOT):
        raise ValueError("private v0.3 reviewer evidence cannot reside in public repository")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_a_v03_original_yaml", type=Path)
    parser.add_argument("reader_a_v03_lock_json", type=Path)
    parser.add_argument("reader_b_v03_original_yaml", type=Path)
    parser.add_argument("reader_b_v03_lock_json", type=Path)
    parser.add_argument("third_source_v03_census_json", type=Path)
    parser.add_argument("private_rule_level_triage_output_json", type=Path)
    args = parser.parse_args()
    try:
        inputs = [
            _private(getattr(args, name))
            for name in (
                "reader_a_v03_original_yaml",
                "reader_a_v03_lock_json",
                "reader_b_v03_original_yaml",
                "reader_b_v03_lock_json",
                "third_source_v03_census_json",
            )
        ]
        output = _private(args.private_rule_level_triage_output_json)
        if output in inputs:
            raise ValueError("private v0.3 triage output must not overwrite source evidence")
        report = audit_v03_independent_source_census(
            raw_a=inputs[0].read_bytes(),
            lock_a=load_coordinator_lock_json(inputs[1].read_bytes()),
            raw_b=inputs[2].read_bytes(),
            lock_b=load_coordinator_lock_json(inputs[3].read_bytes()),
            source_census_json_bytes=inputs[4].read_bytes(),
        )
        data = asdict(report) | {
            "status": report.status,
            "independently_established_requirements_denominator": None,
            "human_adjudication_performed": False,
            "scientific_completeness_certified": False,
            "reviewer_independence_verified_by_software": False,
            "G1_qualified": False,
            "confirmatory_permission": False,
        }
        fd = os.open(
            output,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1
    # Never print private candidate predicates or standards content.
    print(json.dumps({
        "status": report.status,
        "third_source_census_sha256": report.third_source_census_sha256,
        "candidate_rule_count": report.candidate_rule_count,
        "rules_not_found_in_either_reader_count": len(
            report.rules_not_found_in_either_reader
        ),
        "same_locus_but_no_matching_rule_count": len(
            report.same_locus_but_no_matching_rule
        ),
        "G1_qualified": False,
        "confirmatory_permission": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
