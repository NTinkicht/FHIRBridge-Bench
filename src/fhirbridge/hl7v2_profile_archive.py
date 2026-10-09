"""Safely inspect a locally acquired IGAMT validation-profile ZIP archive."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from .hl7v2_profile_bundle import (
    Hl7ProfileIdentity,
    Hl7ProfileMessage,
    ProfileBundleManifest,
    assert_single_oru_r01_profile,
    compute_profile_bundle_manifest,
    inspect_profile_identity,
)

_KNOWN_FILES = (
    "PROFILE.xml",
    "CONSTRAINTS.xml",
    "VALUESETS.xml",
    "VALUESETBINDINGS.xml",
    "COCONSTRAINTS.xml",
    "SLICINGS.xml",
)


@dataclass(frozen=True)
class ProfileArchiveInspection:
    archive_sha256: str
    source_directory: str
    manifest: ProfileBundleManifest
    identity: Hl7ProfileIdentity
    selected_message: Hl7ProfileMessage


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_profile_archive(path: Path) -> ProfileArchiveInspection:
    """Inspect a ZIP without trusting archive paths or extracting unknown files.

    The archive must contain exactly one PROFILE.xml. Known companion files are
    accepted only from the same archive directory as that PROFILE.xml.
    """

    if not path.is_file():
        raise ValueError(f"profile archive is not a file: {path}")

    try:
        archive = ZipFile(path)
    except BadZipFile as exc:
        raise ValueError("profile archive is not a valid ZIP file") from exc

    with archive:
        file_names = [
            name
            for name in archive.namelist()
            if name and not name.endswith("/")
        ]
        profiles = [
            name
            for name in file_names
            if PurePosixPath(name).name == "PROFILE.xml"
        ]
        if len(profiles) != 1:
            raise ValueError(
                "profile archive must contain exactly one PROFILE.xml; "
                f"found {len(profiles)}"
            )

        profile_member = PurePosixPath(profiles[0])
        source_directory = str(profile_member.parent)
        same_directory: dict[str, str] = {}
        for name in file_names:
            member = PurePosixPath(name)
            if member.parent != profile_member.parent:
                continue
            if member.name in _KNOWN_FILES:
                if member.name in same_directory:
                    raise ValueError(
                        f"duplicate profile companion file: {member.name}"
                    )
                same_directory[member.name] = name

        if "PROFILE.xml" not in same_directory:
            raise ValueError("PROFILE.xml was not resolved in selected archive directory")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in _KNOWN_FILES:
                member_name = same_directory.get(filename)
                if member_name is None:
                    continue
                (root / filename).write_bytes(archive.read(member_name))

            manifest = compute_profile_bundle_manifest(root)
            identity = inspect_profile_identity(root)
            selected = assert_single_oru_r01_profile(root)

    return ProfileArchiveInspection(
        archive_sha256=_sha256_file(path),
        source_directory=source_directory,
        manifest=manifest,
        identity=identity,
        selected_message=selected,
    )
