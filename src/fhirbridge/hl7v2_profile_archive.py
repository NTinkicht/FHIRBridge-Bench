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
    ProfileReferenceInventory,
    assert_single_oru_r01_profile,
    compute_profile_bundle_manifest,
    assess_lri_target_reference_signals,
    inspect_profile_identity,
    inspect_profile_reference_inventory,
)


@dataclass(frozen=True)
class ProfileArchiveInspection:
    archive_sha256: str
    source_directory: str
    manifest: ProfileBundleManifest
    identity: Hl7ProfileIdentity
    selected_message: Hl7ProfileMessage
    reference_inventory: ProfileReferenceInventory
    target_reference_signals: dict[str, object]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_profile_archive(path: Path) -> ProfileArchiveInspection:
    """Inspect a ZIP without trusting archive paths or dropping companions.

    The archive must contain exactly one PROFILE.xml. Every safe regular file
    in that profile directory/subtree is retained for hashing so an unknown
    scientific companion cannot silently disappear from the selected bundle.
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
        selected_members: dict[str, str] = {}
        for name in file_names:
            member = PurePosixPath(name)
            if ".." in member.parts:
                continue
            try:
                relative = member.relative_to(profile_member.parent)
            except ValueError:
                continue
            if not relative.parts:
                continue
            relative_name = relative.as_posix()
            if relative_name in selected_members:
                raise ValueError(
                    f"duplicate profile bundle path: {relative_name}"
                )
            selected_members[relative_name] = name

        if "PROFILE.xml" not in selected_members:
            raise ValueError("PROFILE.xml was not resolved in selected archive directory")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_name, member_name in selected_members.items():
                destination = root / PurePosixPath(relative_name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(member_name))

            manifest = compute_profile_bundle_manifest(root)
            identity = inspect_profile_identity(root)
            selected = assert_single_oru_r01_profile(root)
            reference_inventory = inspect_profile_reference_inventory(root)
            target_reference_signals = assess_lri_target_reference_signals(
                reference_inventory
            )

    return ProfileArchiveInspection(
        archive_sha256=_sha256_file(path),
        source_directory=source_directory,
        manifest=manifest,
        identity=identity,
        selected_message=selected,
        reference_inventory=reference_inventory,
        target_reference_signals=target_reference_signals,
    )
