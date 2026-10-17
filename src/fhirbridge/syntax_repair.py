"""Deterministic, semantics-preserving text cleanup for the syntax-repair arm."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class SyntaxRepairResult:
    output: str
    changed: bool
    operations: tuple[str, ...]
    input_sha256: str
    output_sha256: str


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _strip_single_markdown_fence(value: str) -> tuple[str, bool]:
    stripped = value.strip()
    fence = chr(96) * 3
    if not stripped.startswith(fence) or not stripped.endswith(fence):
        return value, False

    lines = stripped.splitlines()
    if len(lines) < 3:
        return value, False
    opening = lines[0].strip().lower()
    if opening not in {fence, fence + "hl7", fence + "text"}:
        return value, False
    if lines[-1].strip() != fence:
        return value, False
    return "\n".join(lines[1:-1]), True


def repair_hl7_text_syntax(raw_output: str) -> SyntaxRepairResult:
    """Apply only wrapper/segment-terminator cleanup.

    This function must never alter text inside a non-empty HL7 segment. It does
    not add/remove fields, change delimiters, rewrite codes, infer values, or
    repair segment ordering.
    """

    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string")

    operations: list[str] = []
    working = raw_output

    if working.startswith("\ufeff"):
        working = working.removeprefix("\ufeff")
        operations.append("remove_utf8_bom")

    fenced, changed = _strip_single_markdown_fence(working)
    if changed:
        working = fenced
        operations.append("remove_single_outer_markdown_fence")

    normalized = working.replace("\r\n", "\n").replace("\r", "\n")
    segments = normalized.split("\n")
    while segments and segments[0] == "":
        segments.pop(0)
    while segments and segments[-1] == "":
        segments.pop()
    nonempty_segments = [segment for segment in segments if segment != ""]
    repaired = "\r".join(nonempty_segments)
    if repaired:
        repaired += "\r"

    if repaired != working:
        operations.append("normalize_segment_terminators_and_outer_blank_lines")

    return SyntaxRepairResult(
        output=repaired,
        changed=repaired != raw_output,
        operations=tuple(dict.fromkeys(operations)),
        input_sha256=_digest(raw_output),
        output_sha256=_digest(repaired),
    )
