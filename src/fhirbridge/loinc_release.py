"""Qualify an official local LOINC release archive without redistributing it."""

from __future__ import annotations

from hashlib import md5, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import BadZipFile, ZipFile

import yaml

from .loinc_snapshot import qualification_to_dict, qualify_loinc_snapshot


def _digest(path: Path, algorithm: str) -> str:
    hasher = md5() if algorithm == "md5" else sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def _requirements_metadata(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    snapshot = document.get("snapshot") if isinstance(document, dict) else None
    if not isinstance(snapshot, dict):
        raise ValueError("LOINC requirements must contain snapshot metadata")
    return snapshot


def qualify_loinc_release_zip(
    zip_path: Path,
    requirements_path: Path,
) -> dict[str, Any]:
    """Verify official checksum, locate Loinc.csv, and qualify required codes."""

    if not zip_path.is_file():
        raise ValueError(f"LOINC release archive is not a file: {zip_path}")

    metadata = _requirements_metadata(requirements_path)
    expected_filename = metadata.get("official_download_filename")
    expected_md5 = metadata.get("official_md5")
    if not isinstance(expected_filename, str) or not expected_filename:
        raise ValueError("official_download_filename must be defined")
    if zip_path.name != expected_filename:
        raise ValueError(
            f"expected release filename {expected_filename!r}, got {zip_path.name!r}"
        )
    if not isinstance(expected_md5, str) or len(expected_md5) != 32:
        raise ValueError("official_md5 must be a 32-character digest")

    observed_md5 = _digest(zip_path, "md5")
    if observed_md5.lower() != expected_md5.lower():
        raise ValueError(
            "LOINC release MD5 mismatch: "
            f"expected {expected_md5.lower()}, observed {observed_md5}"
        )

    zip_sha256 = _digest(zip_path, "sha256")

    try:
        with ZipFile(zip_path) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if name == "Loinc.csv" or name.endswith("/Loinc.csv")
            ]
            if len(candidates) != 1:
                raise ValueError(
                    "LOINC release must contain exactly one Loinc.csv; "
                    f"found {len(candidates)}"
                )
            member = candidates[0]
            csv_bytes = archive.read(member)
    except BadZipFile as exc:
        raise ValueError("LOINC release is not a valid ZIP archive") from exc

    csv_sha256 = sha256(csv_bytes).hexdigest()
    with TemporaryDirectory() as directory:
        csv_path = Path(directory) / "Loinc.csv"
        csv_path.write_bytes(csv_bytes)
        report = qualify_loinc_snapshot(csv_path, requirements_path)

    return {
        "version": report.version,
        "official_filename": zip_path.name,
        "official_md5": observed_md5,
        "zip_sha256": zip_sha256,
        "loinc_csv_member": member,
        "loinc_csv_sha256": csv_sha256,
        "qualification": qualification_to_dict(report),
    }
