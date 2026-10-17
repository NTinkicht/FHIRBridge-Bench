from pathlib import Path

import pytest
import yaml

from fhirbridge.terminology_coverage import (
    assert_loinc_snapshot_covers_benchmark,
    collect_lab_benchmark_loinc_codes,
    required_loinc_codes_from_snapshot_requirements,
)

_REQUIREMENTS = Path("benchmark/loinc_2_83_snapshot_requirements.yaml")


def test_loinc_snapshot_requirements_cover_every_benchmark_loinc_code() -> None:
    benchmark_codes = collect_lab_benchmark_loinc_codes()
    required_codes = required_loinc_codes_from_snapshot_requirements(_REQUIREMENTS)

    assert benchmark_codes == {"24323-8", "2345-7", "2951-2", "2823-3"}
    assert benchmark_codes <= required_codes
    assert_loinc_snapshot_covers_benchmark(_REQUIREMENTS)


def test_loinc_coverage_guard_fails_when_benchmark_code_is_missing(
    tmp_path: Path,
) -> None:
    with _REQUIREMENTS.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    document["required_codes"] = [
        item for item in document["required_codes"] if item["code"] != "2823-3"
    ]
    path = tmp_path / "requirements.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="2823-3"):
        assert_loinc_snapshot_covers_benchmark(path)


def test_required_loinc_code_parser_rejects_duplicate_codes(tmp_path: Path) -> None:
    path = tmp_path / "requirements.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "required_codes": [
                    {"code": "2345-7"},
                    {"code": "2345-7"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate required LOINC code"):
        required_loinc_codes_from_snapshot_requirements(path)
