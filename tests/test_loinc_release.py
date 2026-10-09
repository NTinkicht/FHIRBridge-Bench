from hashlib import md5
from pathlib import Path
from zipfile import ZipFile

import yaml

from fhirbridge.loinc_release import qualify_loinc_release_zip


def _requirements(path: Path, archive_md5: str) -> Path:
    document = {
        "snapshot": {
            "version": "2.83",
            "official_download_filename": "Loinc_2.83.zip",
            "official_md5": archive_md5,
        },
        "required_codes": [
            {
                "code": "2345-7",
                "expected_status": "ACTIVE",
                "expected_long_common_name": (
                    "Glucose [Mass/volume] in Serum or Plasma"
                ),
                "benchmark_role": "observation_code",
            }
        ],
    }
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _release_zip(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "LoincTable/Loinc.csv",
            (
                "LOINC_NUM,STATUS,LONG_COMMON_NAME\n"
                "2345-7,ACTIVE,Glucose [Mass/volume] in Serum or Plasma\n"
            ),
        )


def test_release_zip_qualification_records_hashes_and_required_codes(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "Loinc_2.83.zip"
    _release_zip(archive)
    requirements = _requirements(
        tmp_path / "requirements.yaml",
        md5(archive.read_bytes()).hexdigest(),
    )

    result = qualify_loinc_release_zip(archive, requirements)

    assert result["version"] == "2.83"
    assert result["loinc_csv_member"] == "LoincTable/Loinc.csv"
    assert len(result["zip_sha256"]) == 64
    assert len(result["loinc_csv_sha256"]) == 64
    assert result["qualification"]["all_passed"] is True


def test_release_zip_qualification_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "Loinc_2.83.zip"
    _release_zip(archive)
    requirements = _requirements(
        tmp_path / "requirements.yaml",
        "0" * 32,
    )

    try:
        qualify_loinc_release_zip(archive, requirements)
    except ValueError as exc:
        assert "MD5 mismatch" in str(exc)
    else:
        raise AssertionError("checksum mismatch must fail qualification")


def test_release_zip_qualification_requires_exact_official_filename(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "renamed.zip"
    _release_zip(archive)
    requirements = _requirements(
        tmp_path / "requirements.yaml",
        md5(archive.read_bytes()).hexdigest(),
    )

    try:
        qualify_loinc_release_zip(archive, requirements)
    except ValueError as exc:
        assert "expected release filename" in str(exc)
    else:
        raise AssertionError("renamed release must fail qualification")
