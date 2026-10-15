"""Coordinator-side source provenance checks for the Path B LRI publication.

This module verifies the *bytes* of the official guide and errata against
the archived publication manifest. It never evaluates standards coverage or
authorizes a bounded G1 validator.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "qualification/hl7v2/results/edition5-publication-package-inspection.json"
)
_ROLES = ("implementation_guide", "errata_letter")


def pinned_publication_hashes(manifest_path: Path | None = None) -> dict[str, str]:
    """Read the two archived normative PDF digests, failing closed on bad metadata."""

    document = json.loads((manifest_path or _DEFAULT_MANIFEST).read_text("utf-8"))
    classification = document.get("classification", {})
    if (
        classification.get("is_authoritative_human_readable_publication_package")
        is not True
        or classification.get("is_igamt_validation_bundle") is not False
    ):
        raise ValueError("publication manifest is not a verified PDF-only source")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError("publication manifest entries are missing")
    result: dict[str, str] = {}
    for entry in entries:
        role = entry.get("role")
        if role not in _ROLES or role in result:
            raise ValueError("publication manifest has an unexpected/duplicate role")
        digest = entry.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in digest)
            or set(digest.lower()) == {"0"}
        ):
            raise ValueError("publication manifest has invalid source SHA-256")
        if not str(entry.get("filename", "")).lower().endswith(".pdf"):
            raise ValueError("publication manifest source must be a PDF")
        result[role] = digest.lower()
    if set(result) != set(_ROLES):
        raise ValueError("publication manifest does not pin guide and errata")
    return result


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def verify_publication_files(
    guide_path: Path,
    errata_path: Path,
    *,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    """Reject missing/substituted documents; do not inspect their clinical rules."""

    pinned = pinned_publication_hashes(manifest_path)
    verified: dict[str, dict[str, object]] = {}
    for role, path in (
        ("implementation_guide", guide_path),
        ("errata_letter", errata_path),
    ):
        actual_sha256, size = _file_sha256(path)
        if actual_sha256 != pinned[role]:
            raise ValueError(f"{role} does not match the pinned publication SHA-256")
        verified[role] = {
            "sha256": actual_sha256,
            "size_bytes": size,
        }
    return {
        "status": "SOURCE_BYTES_VERIFIED_ONLY",
        "scientific_qualification": False,
        "documents": verified,
    }
