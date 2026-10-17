"""Strict parsing for private Path B original-response lock JSON files.

The coordinator CLI must not silently accept duplicate keys or nonstandard
JSON numbers when reading a first-round immutable lock. Parser validity does
not attest reviewers, preserve source custody or qualify any G1 instrument.
"""

from __future__ import annotations

import json
from typing import Any

_MAX_LOCK_BYTES = 2 * 1024 * 1024


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate reviewer-lock JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"nonstandard reviewer-lock JSON number: {value}")


def load_coordinator_lock_json(raw: bytes) -> dict[str, Any]:
    """Parse a complete private lock JSON object without resolving ambiguity.

    Source file authenticity is still established by a separate,
    byte-for-byte verify_response_lock check against the response.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > _MAX_LOCK_BYTES:
        raise ValueError("reviewer-lock JSON is missing, nonbytes, or oversized")
    try:
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("reviewer-lock file is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("reviewer-lock file must contain one JSON object")
    # Python dict equality considers False == 0 and True == 1.
    # A lock read with numerical substitutes must never compare equal to
    # create_response_lock's original boolean custody claims.
    for flag in (
        "extraction_declared_complete",
        "initial_extraction_metadata_ready",
        "qualified_G1",
        "adjudication_performed",
    ):
        if flag in data and type(data[flag]) is not bool:
            raise ValueError(f"reviewer-lock flag {flag} must be an actual JSON boolean")
    return data
