"""Tamper-evident capture of original Path B reviewer extraction submissions.

A hash is NOT a signature, proof of human independence, or a substitute for
coordinator-controlled, separately retained read-only evidence.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import yaml

from fhirbridge.lri_required_element_review import (
    assess_required_element_extraction,
    compare_required_element_extractions,
    extraction_comparison_to_dict,
)
from fhirbridge.lri_source_identity import pinned_publication_hashes


class _UniqueKeysExtractionLoader(yaml.SafeLoader):
    """Reject ambiguous mappings and shared YAML aliases in reviewer evidence."""

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):
            raise yaml.composer.ComposerError(
                None, None, "YAML aliases are not allowed in original reviewer submissions",
                self.peek_event().start_mark,
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(
                None, None, "expected a mapping in reviewer YAML", node.start_mark
            )
        seen: set[object] = set()
        for key_node, _ in node.value:
            # YAML's << merge syntax can silently override previously
            # visible reviewer declarations and bypass duplicate-key checks.
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.constructor.ConstructorError(
                    None, None, "YAML merge keys are not allowed", key_node.start_mark
                )
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate reviewer YAML key: {key!r}",
                        key_node.start_mark,
                    )
                seen.add(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    None, None, "unhashable reviewer YAML key", key_node.start_mark
                ) from exc
        return super().construct_mapping(node, deep=deep)


_LOCK_VERSION = "0.1.0"
_REQUIRED_INDEPENDENCE = (
    "other_extractor_output_seen_before_completion",
    "project_required_element_inventory_seen_before_completion",
    "renderer_output_used_as_requirement_evidence",
)


def _response(raw: bytes) -> dict[str, Any]:
    try:
        document = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeysExtractionLoader)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("extraction response is not valid UTF-8 YAML") from exc
    if not isinstance(document, dict) or document.get("schema_version") != "0.2.0":
        raise ValueError("expected an extraction response mapping in schema 0.2.0")
    return document


def _lock_metadata(raw: bytes) -> tuple[dict[str, Any], dict[str, str]]:
    doc = _response(raw)
    source = doc.get("source")
    extractor = doc.get("extractor")
    independence = doc.get("independence")
    if not isinstance(source, dict) or not isinstance(extractor, dict):
        raise ValueError("source/extractor metadata missing from response")
    if not isinstance(independence, dict) or any(
        independence.get(flag) is not False for flag in _REQUIRED_INDEPENDENCE
    ):
        raise ValueError("independence declarations missing or failed")
    if source.get("artifact_type") != "edition5_publication_pdf":
        raise ValueError("Path B lock only accepts the edition5_publication_pdf source")
    pins = pinned_publication_hashes()
    for response_key, pinned_key in (
        ("artifact_sha256", "implementation_guide"),
        ("errata_artifact_sha256", "errata_letter"),
    ):
        value = source.get(response_key)
        if not isinstance(value, str) or value.lower() != pins[pinned_key]:
            raise ValueError("response does not identify the pinned guide and errata")
    identifiers = {
        "extractor_id": extractor.get("extractor_id"),
        "extraction_id": doc.get("extraction_id"),
    }
    if any(
        not isinstance(value, str)
        or not value.strip()
        or "TO_BE_" in value.upper()
        or "TBD" in value.upper()
        for value in identifiers.values()
    ):
        raise ValueError("reviewer/extraction identifiers are missing or placeholders")
    return doc, identifiers


def create_response_lock(raw: bytes) -> dict[str, Any]:
    """Record first submission bytes, including unresolved claims, without editing it."""

    doc, identifiers = _lock_metadata(raw)
    readiness = assess_required_element_extraction(doc)
    return {
        "lock_schema_version": _LOCK_VERSION,
        "status": "RESPONSE_HASHED_NOT_HUMAN_ATTESTED",
        "response_sha256": sha256(raw).hexdigest(),
        **identifiers,
        "source_sha256": pinned_publication_hashes()["implementation_guide"],
        "errata_sha256": pinned_publication_hashes()["errata_letter"],
        "extraction_declared_complete": doc.get("extraction_complete") is True,
        "initial_extraction_metadata_ready": readiness.ready,
        "initial_readiness_blockers": list(readiness.blockers),
        "qualified_G1": False,
        "adjudication_performed": False,
    }


def verify_response_lock(raw: bytes, lock: dict[str, Any]) -> dict[str, Any]:
    """Fail if returned bytes or immutable metadata no longer match the lock."""

    if not isinstance(lock, dict) or lock.get("lock_schema_version") != _LOCK_VERSION:
        raise ValueError("invalid extraction response lock version")
    fresh = create_response_lock(raw)
    if lock != fresh:
        raise ValueError("response does not match its original complete lock record")
    return _response(raw)


def compare_locked_extractions(
    raw_a: bytes,
    lock_a: dict[str, Any],
    raw_b: bytes,
    lock_b: dict[str, Any],
) -> dict[str, Any]:
    """Compare only intact and ready submissions; never adjudicate or qualify."""

    left = verify_response_lock(raw_a, lock_a)
    right = verify_response_lock(raw_b, lock_b)
    if lock_a["extractor_id"] == lock_b["extractor_id"]:
        raise ValueError("the locked reviewers must have different identifiers")
    left_ready = assess_required_element_extraction(left)
    right_ready = assess_required_element_extraction(right)
    if not left_ready.ready or not right_ready.ready:
        return {
            "status": "LOCKED_RESPONSES_NOT_READY_FOR_RULE_COMPARISON",
            "raw_response_hashes": [lock_a["response_sha256"], lock_b["response_sha256"]],
            "readiness_blockers_a": list(left_ready.blockers),
            "readiness_blockers_b": list(right_ready.blockers),
            "adjudication_performed": False,
            "reviewer_independence_verified_by_software": False,
            "G1_qualified": False,
        }
    comparison = extraction_comparison_to_dict(
        compare_required_element_extractions(left, right)
    )
    return {
        "status": "LOCKED_UNADJUDICATED_COMPARISON_ONLY",
        "raw_response_hashes": [lock_a["response_sha256"], lock_b["response_sha256"]],
        "comparison": comparison,
        "reviewer_independence_verified_by_software": False,
        "G1_qualified": False,
    }
