"""Compare a separately received third-source census with two locked reviewers.

PRIVATE COORDINATOR USE ONLY. Do not commit actual reviewer records, source
citations, or output to GitHub. Output never represents validated G1.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from fhirbridge.lri_lock_json import load_coordinator_lock_json
from fhirbridge.path_b_source_census import audit_candidate_source_census


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_original_yaml", type=Path)
    parser.add_argument("first_lock_json", type=Path)
    parser.add_argument("second_original_yaml", type=Path)
    parser.add_argument("second_lock_json", type=Path)
    parser.add_argument("independent_source_census_json", type=Path)
    parser.add_argument("triage_output_json", type=Path)
    args = parser.parse_args()
    try:
        report = audit_candidate_source_census(
            raw_a=args.first_original_yaml.read_bytes(),
            lock_a=load_coordinator_lock_json(args.first_lock_json.read_bytes()),
            raw_b=args.second_original_yaml.read_bytes(),
            lock_b=load_coordinator_lock_json(args.second_lock_json.read_bytes()),
            census_bytes=args.independent_source_census_json.read_bytes(),
        )
        output = asdict(report) | {
            "status": report.status,
            "independently_established_requirements_denominator": (
                report.independently_established_requirements_denominator
            ),
            "standards_completeness_certified": report.standards_completeness_certified,
            "human_adjudication_performed": report.human_adjudication_performed,
            "reviewer_independence_verified_by_software": (
                report.reviewer_independence_verified_by_software
            ),
            "G1_qualified": report.G1_qualified,
            "confirmatory_permission": report.confirmatory_permission,
        }
        # Protect against mistakenly overwriting any original reviewer
        # response or prior report. Caller controls private storage/permissions.
        with args.triage_output_json.open("x", encoding="utf-8") as stream:
            json.dump(output, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1

    print(json.dumps({
        "status": report.status,
        "triage_sha256": sha256(args.triage_output_json.read_bytes()).hexdigest(),
        "candidate_rule_count": report.census_candidate_rule_count,
        "candidate_rule_ids_missing_from_both_count": len(
            report.candidate_rule_ids_missing_from_both
        ),
        "unreviewed_scope_area_count": len(report.unreviewed_source_areas),
        "G1_qualified": False,
        "confirmatory_permission": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
