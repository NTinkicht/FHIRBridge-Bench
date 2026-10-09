"""Freeze helpers for IGAMT-exported HL7 v2 profile resource bundles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

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


@dataclass(frozen=True)
class Hl7ProfileIdentity:
    hl7_version: str | None
    message_type: str | None
    event_type: str | None
    message_structure: str | None


def inspect_profile_identity(root: Path) -> Hl7ProfileIdentity:
    """Extract only standard/message identity from PROFILE.xml.

    This deliberately does not infer LRI edition or errata from free text. Those
    identities must come from the independently acquired profile bundle record.
    The XML inspection is a guard against accidentally freezing a profile for a
    different HL7 version or message structure.
    """

    profile_path = root / "PROFILE.xml"
    if not profile_path.is_file():
        raise ValueError("profile bundle is missing required file(s): PROFILE.xml")

    try:
        document = ElementTree.parse(profile_path)
    except ElementTree.ParseError as exc:
        raise ValueError(f"PROFILE.xml is not well-formed XML: {exc}") from exc

    root = document.getroot()
    hl7_version = root.attrib.get("HL7Version")
    if hl7_version is None:
        hl7_version = next(
            (
                element.attrib["HL7Version"]
                for element in document.iter()
                if element.attrib.get("HL7Version")
            ),
            None,
        )

    message_candidates: list[tuple[str | None, str | None, str | None]] = []
    for element in document.iter():
        message_type = element.attrib.get("MsgType") or element.attrib.get("Type")
        event_type = element.attrib.get("EventType") or element.attrib.get("Event")
        structure = element.attrib.get("MsgStructID") or element.attrib.get("StructID")
        if message_type or event_type or structure:
            message_candidates.append((message_type, event_type, structure))

    preferred = next(
        (
            candidate
            for candidate in message_candidates
            if candidate == ("ORU", "R01", "ORU_R01")
        ),
        message_candidates[0] if message_candidates else (None, None, None),
    )

    return Hl7ProfileIdentity(
        hl7_version=hl7_version,
        message_type=preferred[0],
        event_type=preferred[1],
        message_structure=preferred[2],
    )


def assert_oru_r01_v251_profile(root: Path) -> Hl7ProfileIdentity:
    """Reject a profile bundle that is not clearly HL7 v2.5.1 ORU^R01."""

    identity = inspect_profile_identity(root)
    expected = {
        "hl7_version": "2.5.1",
        "message_type": "ORU",
        "event_type": "R01",
        "message_structure": "ORU_R01",
    }
    observed = {
        "hl7_version": identity.hl7_version,
        "message_type": identity.message_type,
        "event_type": identity.event_type,
        "message_structure": identity.message_structure,
    }
    mismatches = {
        field: {"expected": expected[field], "observed": observed[field]}
        for field in expected
        if observed[field] != expected[field]
    }
    if mismatches:
        raise ValueError(
            "profile is not the required HL7 v2.5.1 ORU^R01 identity: "
            f"{mismatches}"
        )
    return identity
