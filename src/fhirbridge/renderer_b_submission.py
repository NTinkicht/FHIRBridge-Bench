"""Scientific readiness checks for a returned clean-room Renderer B declaration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_EXPECTED_CONTRACT_ID = "F2V-LAB-ORU-R01-001"
_EXPECTED_CONTRACT_VERSION = "0.3.0"
_AI_RENDERER_BLOCKER = (
    "AI-generated mapping code violates the current clean-room independence protocol; "
    "scientific Renderer B comparison requires an independently approved methodology amendment"
)

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
        """Only the original non-AI clean-room protocol may pass this gate."""
        return not self.blockers

    @property
    def ready_for_exploratory_agent_comparison(self) -> bool:
        """Codex prototypes may be compared as development diagnostics only.

        This is *never* scientific independence, normative qualification, or
        permission for confirmatory inference. Every other readiness blocker
        (including exposed A outputs or invalid custodial hashes) still fails.
        """
        return (
            bool(self.blockers)
            and all(blocker == _AI_RENDERER_BLOCKER for blocker in self.blockers)
        )


@lru_cache(maxsize=1)
def _schemas() -> tuple[Draft202012Validator, Draft202012Validator]:
    """Package validators so direct callers cannot bypass CLI shape checks."""
    root = files("fhirbridge")
    # Hatch bundles these schemas into built wheels. An editable install
    # instead points importlib.resources at src/fhirbridge, where the same
    # authoritative schemas live in renderer_validation/schema. Support
    # both layouts without silently accepting a missing schema.
    def read_schema(filename: str) -> dict[str, Any]:
        packaged = root.joinpath(filename)
        if packaged.is_file():
            return json.loads(packaged.read_text(encoding="utf-8"))
        source_file = (
            Path(__file__).resolve().parents[2]
            / "renderer_validation"
            / "schema"
            / filename
        )
        return json.loads(source_file.read_text(encoding="utf-8"))

    declaration = read_schema("renderer_implementation_declaration.schema.json")
    handoff = read_schema("renderer_b_expected_inputs.schema.json")
    Draft202012Validator.check_schema(declaration)
    Draft202012Validator.check_schema(handoff)
    return (
        Draft202012Validator(declaration),
        Draft202012Validator(handoff["properties"]["clean_room_inputs"]),
    )


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def assess_renderer_b_declaration(
    declaration: dict[str, Any],
    *,
    expected_clean_room_inputs: dict[str, Any] | None = None,
) -> RendererBSubmissionReadiness:
    """Check clean-room independence claims beyond JSON-schema shape."""

    blockers: list[str] = []
    warnings: list[str] = []

    if not isinstance(declaration, dict):
        return RendererBSubmissionReadiness(
            blockers=("Renderer B declaration is not an object",), warnings=()
        )
    declaration_schema, handoff_schema = _schemas()
    for error in declaration_schema.iter_errors(declaration):
        blockers.append(
            f"Renderer B declaration schema invalid at {error.json_path} "
            f"({error.validator})"
        )
    if isinstance(expected_clean_room_inputs, dict):
        for error in handoff_schema.iter_errors(expected_clean_room_inputs):
            blockers.append(
                f"custodian clean-room input schema invalid at {error.json_path} "
                f"({error.validator})"
            )

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

    clean_room_inputs = declaration.get("clean_room_inputs")
    if not isinstance(clean_room_inputs, dict):
        blockers.append("clean_room_inputs declaration is missing")
        clean_room_inputs = {}

    for field in (
        "starting_commit",
        "challenge_manifest_sha256",
        "contract_sha256",
    ):
        value = clean_room_inputs.get(field)
        if (
            not isinstance(value, str)
            or not value
            or set(value.lower()) <= {"0"}
        ):
            blockers.append(
                f"clean_room_inputs.{field} is missing or a zero placeholder"
            )

    if expected_clean_room_inputs is None:
        blockers.append(
            "expected clean-room input record was not supplied for comparison"
        )
    elif not isinstance(expected_clean_room_inputs, dict):
        blockers.append("expected clean-room input record is malformed")
    else:
        expected_fields = (
            "repository_full_name",
            "branch",
            "starting_commit",
            "challenge_id",
            "challenge_version",
            "challenge_manifest_sha256",
            "contract_path",
            "contract_sha256",
        )
        for field in expected_fields:
            if clean_room_inputs.get(field) != expected_clean_room_inputs.get(field):
                blockers.append(
                    f"clean_room_inputs.{field} does not match custodian handoff"
                )

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
        blockers.append(_AI_RENDERER_BLOCKER)
        warnings.append(
            "LLM-generated mapping code was used; retain complete prompt/context "
            "provenance and label all comparisons exploratory only"
        )
    elif independence.get("llm_generated_mapping_code_used") is not False:
        blockers.append("LLM-generated mapping code provenance is missing or invalid")

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
        "ready_for_exploratory_agent_comparison": (
            readiness.ready_for_exploratory_agent_comparison
        ),
        "blockers": list(readiness.blockers),
        "warnings": list(readiness.warnings),
    }
