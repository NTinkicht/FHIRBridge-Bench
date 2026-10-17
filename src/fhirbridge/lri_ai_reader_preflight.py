"""Private first-round Mistral AI reader intake; never a human scientific review.

The source license/hosting policy must be checked by an authorized custodian
BEFORE official documents are submitted to a hosted LLM. A coordinator's
explicit authorization declaration here is not independent proof of permission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from fhirbridge.lri_extraction_lock import (
    _response,
    create_response_lock,
    verify_response_lock,
)

_AI_READER_ID = "MISTRAL-READER-A"
_AI_ROLE = "AI_preliminary_extractor"


@dataclass(frozen=True)
class MistralReaderAIntake:
    original_response_lock: dict[str, Any]
    original_response_sha256: str
    declared_source_use_authorized: bool
    metadata_schema_ready: bool
    status: str = "PRIVATE_AI_FIRST_ROUND_NOT_HUMAN_VALIDATED"

    @property
    def independent_human_extraction_received(self) -> bool:
        return False

    @property
    def requirements_denominator_qualified(self) -> bool:
        return False

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def confirmatory_permission(self) -> bool:
        return False


def preflight_mistral_reader_a(
    original_yaml: bytes, *, source_use_authorized: bool
) -> MistralReaderAIntake:
    """Validate an AI-only submission and capture its exact original byte lock.

    The input is untrusted and may be incomplete or UNKNOWN. It is *never*
    updated or silently converted into a clean human-readable submission.
    Duplicate loci, missing constraints, and reviewer uncertainty remain
    explicit blockers for later source-level adjudication.
    """
    if source_use_authorized is not True or type(source_use_authorized) is not bool:
        raise ValueError(
            "private Mistral intake requires affirmative source-use authorization declaration"
        )
    if type(original_yaml) is not bytes or not original_yaml:
        raise ValueError("original Mistral response must be nonempty UTF-8 YAML bytes")

    # Parse the original YAML using the same strict duplicate/alias/merge
    # rejection as the immutable reviewer lock. A disclosed exposure must
    # still be recorded byte-for-byte, even though the scientific intake
    # validator must never accept it as independently obtained.
    submission = _response(original_yaml)
    extractor = submission.get("extractor")
    if not isinstance(extractor, dict):
        raise ValueError("AI extraction reviewer metadata is missing")
    if (
        extractor.get("extractor_id") != _AI_READER_ID
        or extractor.get("role") != _AI_ROLE
    ):
        raise ValueError("Mistral intake must be explicitly identified as AI Reader A")
    # Preserve original AI authorship transparently in the saved bytes. Never
    # quietly relabel the AI's first round as a qualified human submission.
    details = (
        str(extractor.get("prior_project_involvement", ""))
        + " "
        + str(submission.get("notes", "") or "")
    ).lower()
    if "ai-assisted" not in details or "mistral" not in details:
        raise ValueError(
            "Mistral intake requires explicit AI-assisted model provenance"
        )
    # These are explicit submitted *claims*, not API-verified provenance.
    # A floating model alias or absent version is not a reproducible run ID.
    model_id = re.search(r"(?:^|[\\s;])model_id=([a-zA-Z0-9._/-]+)(?:$|[\\s;])", details)
    version = re.search(
        r"(?:^|[\\s;])model_version=([a-zA-Z0-9._/-]+)(?:$|[\\s;])", details
    )
    if (
        model_id is None
        or version is None
        or not model_id.group(1).startswith("mistral-")
        or len(version.group(1)) < 4
        or any(
            token in item
            for item in (model_id.group(1), version.group(1))
            for token in ("latest", "unknown", "to_be_", "tbd", "placeholder")
        )
    ):
        raise ValueError("Mistral intake requires explicit pinned model_id and model_version")
    if submission["extraction_id"] == _AI_READER_ID:
        raise ValueError("Mistral extraction_id needs a separate unique response/run identifier")

    independence = submission.get("independence", {})
    required_flags = (
        "other_extractor_output_seen_before_completion",
        "project_required_element_inventory_seen_before_completion",
        "renderer_output_used_as_requirement_evidence",
    )
    if not isinstance(independence, dict):
        raise ValueError("Mistral response independence disclosure is missing")
    disclosed_exposure = sorted(
        flag for flag in required_flags if independence.get(flag) is not False
    )
    if disclosed_exposure:
        # Do not modify or censor a first response merely because it
        # truthfully admits an isolation failure. This quarantined receipt
        # has a distinct schema/status: it MUST NOT be accepted by the
        # standard verify_response_lock path or as review evidence.
        digest = sha256(original_yaml).hexdigest()
        quarantine = {
            "quarantine_schema_version": "0.1.0",
            "status": "AI_FIRST_ROUND_EXPOSURE_QUARANTINED",
            "response_sha256": digest,
            "declared_exposure_or_missing_independence_flags": disclosed_exposure,
            "qualified_G1": False,
            "adjudication_performed": False,
            "human_independent_extraction": False,
        }
        return MistralReaderAIntake(
            original_response_lock=quarantine,
            original_response_sha256=digest,
            declared_source_use_authorized=True,
            metadata_schema_ready=False,
            status="PRIVATE_AI_EXPOSURE_QUARANTINED_NOT_ELIGIBLE",
        )

    lock = create_response_lock(original_yaml)
    verify_response_lock(original_yaml, lock)
    return MistralReaderAIntake(
        original_response_lock=lock,
        original_response_sha256=lock["response_sha256"],
        declared_source_use_authorized=True,
        metadata_schema_ready=lock["initial_extraction_metadata_ready"],
    )
