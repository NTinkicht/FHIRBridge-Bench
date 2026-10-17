"""Publication digest checks are provenance checks, not standards adjudication."""

import json
import runpy
from hashlib import sha256
from pathlib import Path

import pytest

from fhirbridge.lri_source_identity import (
    pinned_publication_hashes,
    verify_publication_files,
)

_PUB = Path("qualification/hl7v2/results/edition5-publication-package-inspection.json")
_PACKET_BUILDER = "qualification/hl7v2/required_element_review/build_blind_packet.py"


def _fake_manifest(tmp_path: Path, guide: bytes, errata: bytes) -> Path:
    source = json.loads(_PUB.read_text(encoding="utf-8"))
    replacements = {
        "implementation_guide": sha256(guide).hexdigest(),
        "errata_letter": sha256(errata).hexdigest(),
    }
    for entry in source["entries"]:
        entry["sha256"] = replacements[entry["role"]]
    manifest = tmp_path / "publication.json"
    manifest.write_text(json.dumps(source), encoding="utf-8")
    return manifest


def test_packet_pins_match_archived_authoritative_publication() -> None:
    pins = pinned_publication_hashes()
    archived = pinned_publication_hashes(_PUB)
    builder = runpy.run_path(_PACKET_BUILDER)
    assert pins == archived  # Installed wheels use the same immutable provenance.
    assert pins["implementation_guide"] == builder["_SOURCE_SHA256"]
    assert pins["errata_letter"] == builder["_ERRATA_SHA256"]


def test_coordinator_verifies_both_pdf_bytes_without_copying_them(tmp_path: Path) -> None:
    guide, errata = b"%PDF-1.4\nsynthetic guide", b"%PDF-1.4\nsynthetic errata"
    manifest = _fake_manifest(tmp_path, guide, errata)
    guide_path, errata_path = tmp_path / "guide.pdf", tmp_path / "errata.pdf"
    guide_path.write_bytes(guide)
    errata_path.write_bytes(errata)
    report = verify_publication_files(guide_path, errata_path, manifest_path=manifest)
    assert report["status"] == "SOURCE_BYTES_VERIFIED_ONLY"
    assert report["scientific_qualification"] is False
    assert report["documents"]["implementation_guide"]["sha256"] == sha256(guide).hexdigest()
    assert report["documents"]["errata_letter"]["sha256"] == sha256(errata).hexdigest()
    assert "filename" not in str(report)
    assert guide_path.read_bytes() == guide


@pytest.mark.parametrize("corrupt_role", ["guide", "errata"])
def test_coordinator_rejects_substituted_document(tmp_path: Path, corrupt_role: str) -> None:
    guide, errata = b"%PDF-1.4\nguide", b"%PDF-1.4\nerrata"
    manifest = _fake_manifest(tmp_path, guide, errata)
    guide_path, errata_path = tmp_path / "guide.pdf", tmp_path / "errata.pdf"
    guide_path.write_bytes(guide + (b"altered" if corrupt_role == "guide" else b""))
    errata_path.write_bytes(errata + (b"altered" if corrupt_role == "errata" else b""))
    with pytest.raises(ValueError, match="pinned publication SHA-256"):
        verify_publication_files(guide_path, errata_path, manifest_path=manifest)


def test_rejects_missing_errata_pin(tmp_path: Path) -> None:
    source = json.loads(_PUB.read_text(encoding="utf-8"))
    source["entries"] = [source["entries"][0]]
    manifest = tmp_path / "publication.json"
    manifest.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="does not pin guide and errata"):
        pinned_publication_hashes(manifest)


def test_default_pins_are_available_without_repo_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default runtime never relies on source-tree manifest lookup."""

    from fhirbridge import lri_source_identity as identity

    monkeypatch.setattr(
        identity.Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no source-tree file may be read")
        ),
    )
    assert identity.pinned_publication_hashes() == {
        "implementation_guide": "375f02fd5453b06ff1c51841e703c943c3132134fca53a122f5ccfed743461b7",
        "errata_letter": "32eeb375ecb78dd77acb01ed388e30c554688e55a8a4d58df05dd0e7a791700f",
    }
