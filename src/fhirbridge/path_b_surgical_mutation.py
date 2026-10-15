"""Development-only proof that an HL7 control mutates precisely one field.

This is a surgical-diff audit of *provided* synthetic messages, NOT a profile
validator, semantic verifier, assertion that the baseline is valid, or evidence
that a real validator rejected a negative at the expected locus.

A future independently qualified rule-specific validator must still test and
interpret the positive and negative artifacts with original standards evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

_LOCUS = re.compile(r"^(MSH|[A-Z][A-Z0-9]{2})-([1-9][0-9]*)$")
_SEGMENT = re.compile(r"^[A-Z][A-Z0-9]{2}$")


@dataclass(frozen=True, slots=True)
class SurgicalMutationEvidence:
    """Only mechanical one-field change evidence; no conformance verdict."""

    expected_locus: str
    observed_locus: str
    before_sha256: str
    after_sha256: str
    before_value: str
    after_value: str
    @property
    def status(self) -> str:
        return "PREFREEZE_SURGICAL_DIFF_ONLY"

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def validator_expected_locus_failure_confirmed(self) -> bool:
        return False

    @property
    def primary_endpoint_eligible(self) -> bool:
        return False


def _message_fields(message: str) -> list[tuple[str, list[str]]]:
    if not isinstance(message, str) or not message:
        raise ValueError("HL7 control artifact must be nonempty text")

    normalized = message.replace("\r\n", "\r").replace("\n", "\r")
    if not normalized.endswith("\r"):
        raise ValueError("HL7 artifact must terminate with CR")
    lines = normalized[:-1].split("\r")
    if not lines or any(not line for line in lines):
        raise ValueError("missing or empty HL7 segment")
    parsed: list[tuple[str, list[str]]] = []
    for line in lines:
        fields = line.split("|")
        name = fields[0]
        if not _SEGMENT.fullmatch(name) or len(fields) < 2:
            raise ValueError("invalid HL7 segment or non-pipe field separator")
        parsed.append((name, fields))
    if parsed[0][0] != "MSH" or parsed[0][1][1] != "^~\\&":
        raise ValueError("supported synthetic artifact must start with MSH|^~\\&")
    if sum(name == "MSH" for name, _ in parsed) != 1:
        raise ValueError("multiple MSH headers are not supported")
    return parsed


def audit_single_field_mutation(
    before: str,
    after: str,
    *,
    expected_locus: str,
) -> SurgicalMutationEvidence:
    """Reject anything except a single in-place change at the asserted field.

    Fields must already exist on both sides. Group structure and order are
    byte-semantically unchanged (apart from CR versus LF normalization).
    Ambiguous repeated segment names are rejected, not silently assigned.
    """
    match = _LOCUS.fullmatch(expected_locus) if isinstance(expected_locus, str) else None
    if match is None:
        raise ValueError("expected_locus must name one full HL7 field, e.g. OBR-3")
    target, field_number = match.group(1), int(match.group(2))
    if target == "MSH" and field_number < 2:
        raise ValueError("MSH-1 is a delimiter, not a mutable field")
    lhs = _message_fields(before)
    rhs = _message_fields(after)
    if [x[0] for x in lhs] != [x[0] for x in rhs]:
        raise ValueError("segment names/order changed")
    if sum(name == target for name, _ in lhs) != 1:
        raise ValueError("expected target segment must occur exactly once")

    # HL7 MSH-1 is the literal separator and therefore split fields are
    # offset by one compared with ordinary segments.
    field_index = field_number - 1 if target == "MSH" else field_number
    changes: list[tuple[str, int, str, str]] = []
    for (name, left), (_, right) in zip(lhs, rhs, strict=True):
        if len(left) != len(right):
            raise ValueError("field count changed; cannot audit a surgical mutation")
        for index, (a, b) in enumerate(zip(left[1:], right[1:], strict=True), start=1):
            if a != b:
                locus = f"{name}-{index + 1 if name == 'MSH' else index}"
                changes.append((locus, index, a, b))

    if len(changes) != 1:
        raise ValueError("exactly one HL7 field must change")
    observed, index, old, new = changes[0]
    if observed != expected_locus or index != field_index:
        raise ValueError(f"unexpected mutated locus: {observed}")
    if not old or not new:
        raise ValueError("field omission/insertion is not a value-mutation proof")

    return SurgicalMutationEvidence(
        expected_locus=expected_locus,
        observed_locus=observed,
        before_sha256=sha256(before.encode("utf-8")).hexdigest(),
        after_sha256=sha256(after.encode("utf-8")).hexdigest(),
        before_value=old,
        after_value=new,
    )
