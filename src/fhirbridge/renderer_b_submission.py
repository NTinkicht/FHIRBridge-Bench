"""Scientific readiness checks for a returned clean-room Renderer B declaration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPECTED_CONTRACT_ID = "F2V-LAB-ORU-R01-001"
_EXPECTED_CONTRACT_VERSION = "0.2.0"
_PLACEHOLDER_TOKENS = (
    "TO_BE_",
    "TO-BE-",
    "TO BE ",
    "2099-",
)


@dataclass(frozen=True)
class RendererBSubmissionReadiness:
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready_for_differential_comparison(self) -> bool:
        return not self.blockers


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def assess_renderer_b_declaration(
    declaration: dict[str, Any],
) -> RendererBSubmissionReadiness:
    """Check clean-room independence claims beyond JSON-schema shape."""

    blockers: list[str] = []
    warnings: list[str] = []

    renderer_id = declaration.get("renderer_id")
    if _placeholder(renderer_id):
        blockers.append("renderer_id still contains a placeholder")

    contributor = declaration.get("contributor", {})
    contributor_identity = contributor.get("identity")
    if _placeholder(contributor_identity):
        blockers.append("contributor identity still contains a placeholder")

    implementation = declaration.get("implementation", {})
    language = implementation.get("language")
    if _placeholder(language):
        blockers.append("implementation language still contains a placeholder")

    source_commit = implementation.get("source_commit")
    if isinstance(source_commit, str) and set(source_commit.lower()) <= {"0"}:
        blockers.append("implementation source_commit is still a zero placeholder")

    contract = declaration.get("contract", {})
    if contract.get("contract_id") != _EXPECTED_CONTRACT_ID:
        blockers.append("Renderer B declaration references the wrong contract ID")
    if contract.get("contract_version") != _EXPECTED_CONTRACT_VERSION:
        blockers.append("Renderer B declaration references the wrong contract version")

    period = declaration.get("implementation_period", {})
    if period.get("completed_on") is None:
        blockers.append("implementation completion date is not recorded")
    if _placeholder(period.get("started_on")):
        blockers.append("implementation start date still contains a placeholder")

    independence = declaration.get("independence", {})
    false_required = (
        "renderer_a_source_inspected_before_initial_commit",
        "renderer_a_outputs_inspected_before_initial_commit",
        "renderer_a_mapping_code_reused",
        "shared_semantic_mapping_utility_used",
    )
    for field in false_required:
        if independence.get(field) is not False:
            blockers.append(f"clean-room independence condition failed: {field}")

    if independence.get("declaration_complete") is not True:
        blockers.append("independence declaration is not marked complete")

    accidental_exposure = independence.get("accidental_exposure")
    if isinstance(accidental_exposure, str) and accidental_exposure.strip():
        blockers.append("Renderer B implementer declared accidental clean-room exposure")

    if independence.get("llm_generated_mapping_code_used") is True:
        warnings.append(
            "LLM-generated mapping code was used; retain prompt/context provenance "
            "to demonstrate Renderer A material was not exposed"
        )

    if isinstance(language, str) and "python" in language.lower():
        rationale = independence.get("same_language_as_renderer_a_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            blockers.append(
                "Python Renderer B requires an explicit same-language independence rationale"
            )

    standards = declaration.get("standards_sources", [])
    names = " ".join(
        str(item.get("name", ""))
        for item in standards
        if isinstance(item, dict)
    ).lower()
    if "fhir" not in names:
        blockers.append("standards_sources does not identify a FHIR source")
    if "lri" not in names and "laboratory results interface" not in names:
        blockers.append("standards_sources does not identify the LRI target guide")

    unsupported = declaration.get("known_unsupported_cases", [])
    if any(_placeholder(item) for item in unsupported):
        blockers.append("known_unsupported_cases still contains a placeholder")

    return RendererBSubmissionReadiness(
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )


def renderer_b_readiness_to_dict(
    readiness: RendererBSubmissionReadiness,
) -> dict[str, Any]:
    return {
        "ready_for_differential_comparison": (
            readiness.ready_for_differential_comparison
        ),
        "blockers": list(readiness.blockers),
        "warnings": list(readiness.warnings),
    }
