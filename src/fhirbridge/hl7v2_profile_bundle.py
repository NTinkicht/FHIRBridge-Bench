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
class Hl7ProfileMessage:
    identifier: str | None
    description: str | None
    message_type: str | None
    event_type: str | None
    message_structure: str | None


def inspect_profile_messages(root: Path) -> tuple[Hl7ProfileMessage, ...]:
    """Return declared message profiles in document order.

    IGAMT/NIST exports have used more than one attribute naming convention.
    This parser recognizes both the historical Message Type/Event/StructID form
    and MsgType/EventType/MsgStructID forms without using free-text labels as
    message identity.
    """

    profile_path = root / "PROFILE.xml"
    if not profile_path.is_file():
        raise ValueError("profile bundle is missing required file(s): PROFILE.xml")
    try:
        document = ElementTree.parse(profile_path)
    except ElementTree.ParseError as exc:
        raise ValueError(f"PROFILE.xml is not well-formed XML: {exc}") from exc

    messages: list[Hl7ProfileMessage] = []
    for element in document.iter():
        message_type = element.attrib.get("MsgType") or element.attrib.get("Type")
        event_type = element.attrib.get("EventType") or element.attrib.get("Event")
        structure = element.attrib.get("MsgStructID") or element.attrib.get("StructID")
        if not (message_type or event_type or structure):
            continue
        messages.append(
            Hl7ProfileMessage(
                identifier=element.attrib.get("ID"),
                description=element.attrib.get("Description"),
                message_type=message_type,
                event_type=event_type,
                message_structure=structure,
            )
        )
    return tuple(messages)

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

    root_element = document.getroot()
    hl7_version = root_element.attrib.get("HL7Version")
    if hl7_version is None:
        hl7_version = next(
            (
                element.attrib["HL7Version"]
                for element in document.iter()
                if element.attrib.get("HL7Version")
            ),
            None,
        )

    messages = inspect_profile_messages(root)
    preferred_message = next(
        (
            message
            for message in messages
            if (
                message.message_type,
                message.event_type,
                message.message_structure,
            )
            == ("ORU", "R01", "ORU_R01")
        ),
        messages[0] if messages else None,
    )

    return Hl7ProfileIdentity(
        hl7_version=hl7_version,
        message_type=(preferred_message.message_type if preferred_message else None),
        event_type=(preferred_message.event_type if preferred_message else None),
        message_structure=(
            preferred_message.message_structure if preferred_message else None
        ),
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


def assert_single_oru_r01_profile(root: Path) -> Hl7ProfileMessage:
    """Require exactly one ORU^R01 profile for deterministic local validation.

    The CDC wrapper validates against the first message profile exposed by the
    underlying NIST profile. A confirmatory bundle with multiple ORU^R01
    variants would therefore make profile selection implicit. FHIRBridge-Bench
    refuses that ambiguity: the acquired bundle must be a single selected
    ORU^R01 profile export, or a documented selector-capable validation path
    must replace this wrapper before freeze.
    """

    assert_oru_r01_v251_profile(root)
    matches = [
        message
        for message in inspect_profile_messages(root)
        if (
            message.message_type,
            message.event_type,
            message.message_structure,
        )
        == ("ORU", "R01", "ORU_R01")
    ]
    if len(matches) != 1:
        identifiers = [message.identifier for message in matches]
        raise ValueError(
            "confirmatory profile must contain exactly one ORU^R01 message; "
            f"found {len(matches)} with identifiers {identifiers}"
        )

    selected = matches[0]
    messages = inspect_profile_messages(root)
    if not messages or messages[0] != selected:
        first_identifier = messages[0].identifier if messages else None
        raise ValueError(
            "CDC ProfileManager validates the first declared message profile, "
            "but the selected ORU^R01 profile is not first. "
            f"first message identifier={first_identifier!r}, "
            f"ORU identifier={selected.identifier!r}. "
            "Acquire a single-message ORU export or use a selector-capable "
            "validation harness before confirmatory freeze."
        )
    return selected
