"""Cryptographic provenance helpers for frozen local dependency artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class ArtifactDigest:
    path: str
    sha256: str
    size_bytes: int


def sha256_file(path: Path) -> ArtifactDigest:
    """Return SHA-256 and size for one local artifact."""

    if not path.is_file():
        raise ValueError(f"artifact is not a file: {path}")
    digest = sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return ArtifactDigest(
        path=str(path),
        sha256=digest.hexdigest(),
        size_bytes=size,
    )


def assert_sha256(path: Path, expected_sha256: str) -> ArtifactDigest:
    """Fail closed when a local artifact does not match the frozen digest."""

    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in expected_sha256
    ):
        raise ValueError("expected_sha256 must be a 64-character hexadecimal digest")
    observed = sha256_file(path)
    if observed.sha256.lower() != expected_sha256.lower():
        raise ValueError(
            "artifact SHA-256 mismatch: "
            f"expected {expected_sha256.lower()}, observed {observed.sha256}"
        )
    return observed
