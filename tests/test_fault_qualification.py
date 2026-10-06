import pytest

from fhirbridge.fault_qualification import (
    FaultQualificationCase,
    qualify_seeded_faults,
)


def test_class_detection_and_exact_resolution_are_reported_separately() -> None:
    cases = [
        FaultQualificationCase(
            case_id="F001-a",
            expected_classifications=("FABRICATION",),
            expected_severity="S2",
            observed_classifications=("VERIFIED_EQUIVALENT", "FABRICATION"),
            observed_severities=("S2",),
        ),
        FaultQualificationCase(
            case_id="MF003-a",
            expected_classifications=("OMISSION", "FABRICATION"),
            expected_severity="S3",
            observed_classifications=(
                "VERIFIED_EQUIVALENT",
                "OMISSION",
                "FABRICATION",
            ),
            observed_severities=("S3", "S2"),
        ),
        FaultQualificationCase(
            case_id="F006-a",
            expected_classifications=("MISATTRIBUTION",),
            expected_severity="S3",
            observed_classifications=("OMISSION",),
            observed_severities=("S3",),
        ),
    ]

    report = qualify_seeded_faults(cases)

    assert report.total_cases == 3
    assert report.all_expected_classes_detected.successes == 2
    assert report.all_expected_classes_detected.total == 3
    assert report.exact_class_resolution.successes == 2
    assert report.by_class["FABRICATION"].successes == 2
    assert report.by_class["FABRICATION"].total == 2
    assert report.by_class["OMISSION"].successes == 1
    assert report.by_class["MISATTRIBUTION"].successes == 0
    assert report.unresolved_case_ids == ("F006-a",)


def test_extra_error_class_preserves_recall_but_fails_strict_resolution() -> None:
    report = qualify_seeded_faults(
        [
            FaultQualificationCase(
                case_id="F002-extra",
                expected_classifications=("CORRUPTION",),
                expected_severity="S3",
                observed_classifications=("CORRUPTION", "FABRICATION"),
                observed_severities=("S3", "S2"),
            )
        ]
    )

    assert report.all_expected_classes_detected.estimate == 1.0
    assert report.exact_class_resolution.estimate == 0.0
    assert report.by_class["CORRUPTION"].estimate == 1.0
    assert report.extra_error_case_ids == ("F002-extra",)


def test_expected_severity_strata_report_class_detection_with_intervals() -> None:
    report = qualify_seeded_faults(
        [
            FaultQualificationCase(
                case_id="s2-hit",
                expected_classifications=("FABRICATION",),
                expected_severity="S2",
                observed_classifications=("FABRICATION",),
                observed_severities=("S2",),
            ),
            FaultQualificationCase(
                case_id="s3-hit",
                expected_classifications=("CORRUPTION",),
                expected_severity="S3",
                observed_classifications=("CORRUPTION",),
                observed_severities=("S3",),
            ),
            FaultQualificationCase(
                case_id="s3-miss",
                expected_classifications=("OMISSION",),
                expected_severity="S3",
                observed_classifications=("INDETERMINATE",),
                observed_severities=(),
            ),
        ]
    )

    assert report.by_expected_severity["S2"].estimate == 1.0
    assert report.by_expected_severity["S3"].estimate == pytest.approx(0.5)
    assert report.severity_at_least_expected.successes == 2
    for rate in (
        report.exact_class_resolution,
        report.all_expected_classes_detected,
        report.severity_at_least_expected,
        *report.by_class.values(),
        *report.by_expected_severity.values(),
    ):
        assert 0 <= rate.lower <= rate.estimate <= rate.upper <= 1


def test_invalid_case_definitions_are_rejected() -> None:
    with pytest.raises(ValueError, match="case_id"):
        FaultQualificationCase(
            case_id="",
            expected_classifications=("CORRUPTION",),
            expected_severity="S3",
            observed_classifications=("CORRUPTION",),
        )

    with pytest.raises(ValueError, match="must not be empty"):
        FaultQualificationCase(
            case_id="x",
            expected_classifications=(),
            expected_severity="S3",
            observed_classifications=(),
        )

    with pytest.raises(ValueError, match="unsupported expected"):
        FaultQualificationCase(
            case_id="x",
            expected_classifications=("VERIFIED_EQUIVALENT",),
            expected_severity="S0",
            observed_classifications=("VERIFIED_EQUIVALENT",),
        )

    with pytest.raises(ValueError, match="expected_severity"):
        FaultQualificationCase(
            case_id="x",
            expected_classifications=("CORRUPTION",),
            expected_severity="major",
            observed_classifications=("CORRUPTION",),
        )

    with pytest.raises(ValueError, match="observed severities"):
        FaultQualificationCase(
            case_id="x",
            expected_classifications=("CORRUPTION",),
            expected_severity="S3",
            observed_classifications=("CORRUPTION",),
            observed_severities=("major",),
        )


def test_empty_or_duplicate_case_sets_are_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        qualify_seeded_faults([])

    duplicate = FaultQualificationCase(
        case_id="duplicate",
        expected_classifications=("CORRUPTION",),
        expected_severity="S3",
        observed_classifications=("CORRUPTION",),
        observed_severities=("S3",),
    )
    with pytest.raises(ValueError, match="unique"):
        qualify_seeded_faults([duplicate, duplicate])
