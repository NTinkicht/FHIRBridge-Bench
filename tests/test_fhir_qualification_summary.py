from pathlib import Path

import pytest

from qualification.fhir.summarize_validation import (
    summarize_directory,
    summarize_log,
)


def test_summarize_fhir_validator_log_extracts_final_counts(tmp_path: Path) -> None:
    path = tmp_path / "LAB-001.log"
    path.write_text(
        "loading\nSuccess: 0 errors, 9 warnings, 2 notes\n",
        encoding="utf-8",
    )

    summary = summarize_log(path)

    assert summary == {
        "file": "LAB-001.log",
        "errors": 0,
        "warnings": 9,
        "notes": 2,
    }


def test_summarize_directory_retains_warning_and_note_counts(tmp_path: Path) -> None:
    (tmp_path / "LAB-001.log").write_text(
        "Success: 0 errors, 9 warnings, 2 notes\n",
        encoding="utf-8",
    )
    (tmp_path / "LAB-002.log").write_text(
        "Success: 0 errors, 3 warnings, 1 notes\n",
        encoding="utf-8",
    )

    summary = summarize_directory(tmp_path)

    assert summary["fixture_count"] == 2
    assert summary["zero_error_fixture_count"] == 2
    assert summary["total_errors"] == 0
    assert summary["total_warnings"] == 12
    assert summary["total_notes"] == 3


def test_summarize_log_fails_closed_without_validator_summary(tmp_path: Path) -> None:
    path = tmp_path / "LAB-001.log"
    path.write_text("validator crashed before summary\n", encoding="utf-8")

    with pytest.raises(ValueError, match="summary not found"):
        summarize_log(path)


def test_summarize_directory_rejects_empty_evidence_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="no FHIR qualification logs"):
        summarize_directory(tmp_path)
