from pathlib import Path

from fhirbridge.loinc_snapshot import (
    load_required_codes,
    qualification_to_dict,
    qualify_loinc_snapshot,
)

_REQUIREMENTS = Path("benchmark/loinc_2_83_snapshot_requirements.yaml")


def _write_csv(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.write_text(
        "LOINC_NUM,STATUS,LONG_COMMON_NAME\n"
        + "".join(f"{code},{status},{name}\n" for code, status, name in rows),
        encoding="utf-8",
    )


def test_required_loinc_snapshot_codes_are_unique_and_versioned() -> None:
    version, required = load_required_codes(_REQUIREMENTS)

    assert version == "2.83"
    assert {item.code for item in required} == {
        "24323-8",
        "2345-7",
        "2951-2",
        "2823-3",
    }


def test_local_loinc_snapshot_qualification_passes_exact_required_subset(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "Loinc.csv"
    _write_csv(
        csv_path,
        [
            (
                "24323-8",
                "ACTIVE",
                "Comprehensive metabolic 2000 panel - Serum or Plasma",
            ),
            (
                "2345-7",
                "ACTIVE",
                "Glucose [Mass/volume] in Serum or Plasma",
            ),
            (
                "2951-2",
                "ACTIVE",
                "Sodium [Moles/volume] in Serum or Plasma",
            ),
            (
                "2823-3",
                "ACTIVE",
                "Potassium [Moles/volume] in Serum or Plasma",
            ),
        ],
    )

    report = qualify_loinc_snapshot(csv_path, _REQUIREMENTS)

    assert report.all_passed
    assert report.passed_required == 4
    assert qualification_to_dict(report)["version"] == "2.83"


def test_local_loinc_snapshot_qualification_fails_missing_or_changed_content(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "Loinc.csv"
    _write_csv(
        csv_path,
        [
            (
                "24323-8",
                "DEPRECATED",
                "Comprehensive metabolic 2000 panel - Serum or Plasma",
            ),
            (
                "2345-7",
                "ACTIVE",
                "Unexpected renamed glucose term",
            ),
        ],
    )

    report = qualify_loinc_snapshot(csv_path, _REQUIREMENTS)

    assert not report.all_passed
    results = {item.code: item for item in report.results}
    assert results["24323-8"].present
    assert not results["24323-8"].status_match
    assert not results["2345-7"].name_match
    assert not results["2951-2"].present
    assert not results["2823-3"].present
