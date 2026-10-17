"""Private Mistral Reader A v0.3 rule-level intake (no scientific attestation).

The legacy v0.2 intake remains unchanged and cannot verify these versioned
originals. Hosting and source licensing authorization is a separate
coordinator obligation, not an inference made by this software.
"""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

from fhirbridge.lri_ai_reader_preflight import MistralReaderAIntake
from fhirbridge.lri_rule_level_extraction_v03 import (
    create_v03_response_lock,
    parse_v03_original,
    verify_v03_response_lock,
)

_ID = "MISTRAL-READER-A"
_ROLE = "AI_preliminary_extractor"
_FLAGS = (
    "other_extractor_output_seen_before_completion",
    "project_required_element_inventory_seen_before_completion",
    "renderer_output_used_as_requirement_evidence",
)
_PROVENANCE = re.compile(
    r"(?:^|[\s;])(?P<key>model_id|model_version)=(?P<value>[a-zA-Z0-9._/-]+)(?=$|[\s;])"
)


def _model_provenance(doc: dict[str, Any]) -> None:
    ext = doc.get("extractor")
    if type(ext) is not dict or ext.get("extractor_id") != _ID or ext.get("role") != _ROLE:
        raise ValueError("v0.3 Mistral must declare AI Reader A, never a human reviewer")
    if doc.get("extraction_id") == _ID:
        raise ValueError("v0.3 Mistral needs a distinct original run identifier")
    narrative = (
        str(ext.get("prior_project_involvement") or "")
        + " "
        + str(doc.get("notes") or "")
    ).lower()
    if "ai-assisted" not in narrative or "mistral" not in narrative:
        raise ValueError("v0.3 Mistral AI-assisted provenance is required")
    tokens: dict[str, list[str]] = {}
    for match in _PROVENANCE.finditer(narrative):
        tokens.setdefault(match["key"], []).append(match["value"])
    # Ambiguous repeated keys could hide a false model identity.
    if set(tokens) != {"model_id", "model_version"} or any(
        len(v) != 1 for v in tokens.values()
    ):
        raise ValueError("v0.3 Mistral requires unique model_id and model_version")
    model_id, version = tokens["model_id"][0], tokens["model_version"][0]
    if (
        not model_id.startswith("mistral-")
        or len(version) < 4
        or any(
            p in x
            for p in ("unknown", "latest", "placeholder", "to_be_", "tbd")
            for x in (model_id, version)
        )
    ):
        raise ValueError("v0.3 Mistral model ID/version cannot be floating or placeholder")


def preflight_mistral_reader_a_v03(
    raw: bytes, *, source_use_authorized: bool
) -> MistralReaderAIntake:
    """Capture a byte-exact AI original without certifying an Edition 5 rule.

    A disclosed breach is retained with a *separate* quarantine lock that
    cannot pass normal v0.3 review verification. No false independence
    declarations are required to preserve a problematic original.
    """
    if type(source_use_authorized) is not bool or not source_use_authorized:
        raise ValueError("source-use authorization declaration required before v0.3 intake")
    doc = parse_v03_original(raw)
    _model_provenance(doc)
    independence = doc.get("independence")
    if type(independence) is not dict:
        raise ValueError("missing v0.3 independence disclosures")
    problems = sorted(flag for flag in _FLAGS if independence.get(flag) is not False)
    if problems:
        digest = sha256(raw).hexdigest()
        quarantine = {
            "quarantine_schema_version": "0.3.0",
            "status": "AI_RULE_LEVEL_V03_EXPOSURE_QUARANTINED",
            "response_sha256": digest,
            "disclosed_or_missing_independence_flags": problems,
            "human_independent_extraction": False,
            "qualified_G1": False,
            "adjudication_performed": False,
            "confirmatory_permission": False,
        }
        return MistralReaderAIntake(
            original_response_lock=quarantine,
            original_response_sha256=digest,
            declared_source_use_authorized=True,
            metadata_schema_ready=False,
            status="PRIVATE_AI_V03_EXPOSURE_QUARANTINED_NOT_ELIGIBLE",
        )
    lock = create_v03_response_lock(raw)
    verify_v03_response_lock(raw, lock)
    return MistralReaderAIntake(
        original_response_lock=lock,
        original_response_sha256=lock["response_sha256"],
        declared_source_use_authorized=True,
        metadata_schema_ready=lock["metadata_ready"],
        status="PRIVATE_AI_V03_RULE_LEVEL_NOT_HUMAN_VALIDATED",
    )
