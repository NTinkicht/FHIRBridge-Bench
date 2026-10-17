"""Private first-round Mistral AI reader intake; never a human scientific review.

The source license/hosting policy must be checked by an authorized custodian
BEFORE official documents are submitted to a hosted LLM. A coordinator's
explicit authorization declaration here is not independent proof of permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fhirbridge.lri_extraction_lock import (
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

    lock = create_response_lock(original_yaml)
    submission = verify_response_lock(original_yaml, lock)
    extractor = submission["extractor"]
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
    if submission["extraction_id"] == _AI_READER_ID:
        raise ValueError("Mistral extraction_id needs a separate unique response/run identifier")

    return MistralReaderAIntake(
        original_response_lock=lock,
        original_response_sha256=lock["response_sha256"],
        declared_source_use_authorized=True,
        metadata_schema_ready=lock["initial_extraction_metadata_ready"],
    )
