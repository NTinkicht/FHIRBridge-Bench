"""Source-role/locus probes for synthetic pre-freeze Path B experiments.

These are *fixture assertions* about separately authored synthetic facts,
not independently adjudicated HL7 LRI Edition 5 mappings. In particular,
a source-grounded accession or order ID in the wrong field is not
automatically a valid projection. No result from this module can be
used as G1 validity or a confirmatory semantic verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

_ROLE_FIELDS = {
    "ORC-2": ("ORC", 2),
    "ORC-3": ("ORC", 3),
    "OBR-2": ("OBR", 2),
    "OBR-3": ("OBR", 3),
}
_ORDER_ROLES = frozenset({"placer", "filler"})


@dataclass(frozen=True)
class AuthoredIdentifierRoles:
    """Three distinct, explicitly authored synthetic identifier roles."""

    accession: str
    placer: str
    filler: str
    service_request_code: str
    diagnostic_report_code: str

    def __post_init__(self) -> None:
        identifiers = (self.accession, self.placer, self.filler)
        for value in (*identifiers, self.service_request_code, self.diagnostic_report_code):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("synthetic role values and codes must be nonempty strings")
            if any(char in value for char in ("|", "\r", "\n")):
                raise ValueError("synthetic values must not contain HL7 delimiters")
        if len(set(identifiers)) != 3:
            raise ValueError("accession, placer and filler must be distinct")

    def identifier_by_role(self) -> dict[str, str]:
        return {
            "accession": self.accession,
            "placer": self.placer,
            "filler": self.filler,
        }


@dataclass(frozen=True)
class FixtureLocusEvidence:
    locus: str
    fixture_expected_role: str
    observed_value: str
    observed_authored_role: str | None
    source_grounded: bool | None
    matches_fixture_expectation: bool
    observation: str


@dataclass(frozen=True)
class DevelopmentRoleProbe:
    loci: tuple[FixtureLocusEvidence, ...]
    order_code_observation: str
    status: str = "PREFREEZE_FIXTURE_ASSERTIONS_ONLY"
    semantic_verdict: str = "INDETERMINATE"
    G1_qualified: bool = False
    primary_endpoint_eligible: bool = False

    @property
    def mismatched_loci(self) -> tuple[str, ...]:
        return tuple(item.locus for item in self.loci if not item.matches_fixture_expectation)


def _segments_by_name(message: str) -> dict[str, list[str]]:
    if not isinstance(message, str):
        raise ValueError("HL7 fixture must be a text message")
    lines = [
        line
        for line in message.replace("\r\n", "\r").replace("\n", "\r").split("\r")
        if line.strip()
    ]
    names = [line.split("|", 1)[0] for line in lines]
    if names.count("ORC") != 1 or names.count("OBR") != 1:
        raise ValueError("probe requires exactly one ORC and one OBR group")
    if names.index("ORC") >= names.index("OBR"):
        raise ValueError("ORC must precede its OBR in the synthetic fixture")
    return {
        "ORC": lines[names.index("ORC")].split("|"),
        "OBR": lines[names.index("OBR")].split("|"),
    }


def inspect_authored_identifier_loci(
    message: str,
    *,
    source: AuthoredIdentifierRoles,
    fixture_expected_loci: Mapping[str, str],
) -> DevelopmentRoleProbe:
    """Check explicitly asserted synthetic loci without qualifying an HL7 rule.

    The caller, NOT this library, supplies each provisional role-to-field
    assignment. This accepts only the four order-ID positions, requires all
    four positions to be assessed, and will not infer a mapping from a
    source-authored accession or from ORC/OBR mirror equality.
    """
    if not isinstance(fixture_expected_loci, Mapping):
        raise ValueError("fixture_expected_loci must be a mapping")
    if set(fixture_expected_loci) != set(_ROLE_FIELDS):
        raise ValueError("all four ORC/OBR identifier loci must be asserted")
    if any(role not in _ORDER_ROLES for role in fixture_expected_loci.values()):
        raise ValueError("only explicit placer/filler fixture expectations are allowed")
    segments = _segments_by_name(message)
    authorship = source.identifier_by_role()
    observed: list[FixtureLocusEvidence] = []
    for locus, (segment, number) in _ROLE_FIELDS.items():
        fields = segments[segment]
        value = fields[number] if number < len(fields) else ""
        role = next((key for key, authored in authorship.items() if value == authored), None)
        expected = fixture_expected_loci[locus]
        matched = value == authorship[expected]
        if not value:
            observation = "ABSENT"
        elif matched:
            observation = "FIXTURE_ROLE_MATCH"
        elif role is not None:
            observation = "OTHER_SOURCE_AUTHORED_ROLE"
        else:
            observation = "NOT_SOURCE_AUTHORED"
        observed.append(
            FixtureLocusEvidence(
                locus=locus,
                fixture_expected_role=expected,
                observed_value=value,
                observed_authored_role=role,
                source_grounded=(role is not None) if value else None,
                matches_fixture_expectation=matched,
                observation=observation,
            )
        )

    return DevelopmentRoleProbe(
        loci=tuple(observed),
        order_code_observation=(
            "DISTINCT_SERVICE_REQUEST_AND_REPORT_CODES_UNRESOLVED"
            if source.service_request_code != source.diagnostic_report_code
            else "NO_SOURCE_CODE_DIVERGENCE_OBSERVED"
        ),
    )
