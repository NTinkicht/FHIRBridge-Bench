"""Private first-round JSON locks must not admit ambiguous JSON decoding."""

import json

import pytest

from fhirbridge.lri_lock_json import load_coordinator_lock_json


def test_valid_private_lock_object_parses_without_qualification_claim() -> None:
    doc = {
        "lock_schema_version": "0.1.0",
        "status": "RESPONSE_HASHED_NOT_HUMAN_ATTESTED",
        "qualified_G1": False,
        "reviewer_independence_verified_by_software": False,
        "nested": {"source_sha256": "a" * 64},
    }
    assert load_coordinator_lock_json(json.dumps(doc).encode("utf-8")) == doc


@pytest.mark.parametrize(
    "raw",
    [
        b'{"qualified_G1": true, "qualified_G1": false}',
        b'{"source_sha256": "BAD", "source_sha256": "VALID"}',
        b'{"readiness": {"verified": true, "verified": false}}',
        b'{"reader": {"id": "A", "id": "B"}}',
    ],
)
def test_duplicate_json_keys_are_rejected_at_any_depth(raw: bytes) -> None:
    with pytest.raises(ValueError, match="duplicate reviewer-lock JSON key"):
        load_coordinator_lock_json(raw)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nonstandard_json_numbers_never_enter_a_review_lock(token: str) -> None:
    with pytest.raises(ValueError, match="nonstandard reviewer-lock JSON"):
        load_coordinator_lock_json(
            ('{"response_sha256": ' + token + "}").encode("utf-8")
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"truncated": ',
        b"\xff\xfe",
        b"[]",
        b"null",
        b"1",
        b"",
        b" " * (2 * 1024 * 1024 + 1),
    ],
)
def test_invalid_nonobject_or_oversized_lock_rejected(raw: bytes) -> None:
    with pytest.raises(ValueError, match="reviewer-lock"):
        load_coordinator_lock_json(raw)


def test_source_lock_hash_requires_exact_bytes_not_trimmed_content() -> None:
    raw = b'{"source_sha256": "original", "qualified_G1": false}'
    result = load_coordinator_lock_json(raw)
    assert result["source_sha256"] == "original"
    assert result["qualified_G1"] is False
    # The parser does not promote any author or scientific readiness state.
    assert "reviewer_independence_verified_by_software" not in result
