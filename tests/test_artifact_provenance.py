from hashlib import sha256
from pathlib import Path

import pytest

from fhirbridge.artifact_provenance import assert_sha256, sha256_file


def test_sha256_file_records_digest_and_size(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"fhirbridge")

    result = sha256_file(artifact)

    assert result.size_bytes == len(b"fhirbridge")
    assert result.sha256 == sha256(b"fhirbridge").hexdigest()
    assert result.path == str(artifact)


def test_assert_sha256_accepts_exact_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"pinned")
    expected = sha256(b"pinned").hexdigest()

    result = assert_sha256(artifact, expected.upper())

    assert result.sha256 == expected


def test_assert_sha256_rejects_tampered_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        assert_sha256(artifact, sha256(b"expected").hexdigest())


@pytest.mark.parametrize("digest", ["", "abc", "g" * 64])
def test_assert_sha256_rejects_invalid_digest(digest: str, tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"x")

    with pytest.raises(ValueError, match="64-character hexadecimal"):
        assert_sha256(artifact, digest)


def test_sha256_file_rejects_missing_artifact(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a file"):
        sha256_file(tmp_path / "missing.bin")
