"""Freeze helpers for IGAMT-exported HL7 v2 profile resource bundles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

_REQUIRED_FILES = ("PROFILE.xml",)
_OPTIONAL_FILES = (
    "CONSTRAINTS.xml",
    "VALUESETS.xml",
    "VALUESETBINDINGS.xml",
    "COCONSTRAINTS.xml",
    "SLICINGS.xml",
)


@dataclass(frozen=True)
class ProfileBundleFile:
    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ProfileBundleManifest:
    files: tuple[ProfileBundleFile, ...]
    aggregate_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "files": [
                {
                    "name": item.name,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in self.files
            ],
            "aggregate_sha256": self.aggregate_sha256,
        }


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def compute_profile_bundle_manifest(root: Path) -> ProfileBundleManifest:
    """Hash one local IGAMT profile bundle deterministically.

    PROFILE.xml is mandatory. Known IGAMT companion artifacts are included
    when present. Unknown files are intentionally ignored so editor metadata or
    operating-system files cannot silently change the scientific profile hash.
    """

    if not root.is_dir():
        raise ValueError(f"profile bundle root is not a directory: {root}")

    missing = [name for name in _REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError(
            "profile bundle is missing required file(s): " + ", ".join(missing)
        )

    files: list[ProfileBundleFile] = []
    aggregate = sha256()
    for name in (*_REQUIRED_FILES, *_OPTIONAL_FILES):
        path = root / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        digest = _hash_bytes(data)
        files.append(
            ProfileBundleFile(
                name=name,
                sha256=digest,
                size_bytes=len(data),
            )
        )
        aggregate.update(name.encode("utf-8"))
        aggregate.update(bytes([0]))
        aggregate.update(digest.encode("ascii"))
        aggregate.update(bytes([10]))

    return ProfileBundleManifest(
        files=tuple(files),
        aggregate_sha256=aggregate.hexdigest(),
    )
