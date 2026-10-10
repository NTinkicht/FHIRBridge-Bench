"""Safety checks for the confirmatory instrument/sealed-set freeze.

Schema validity establishes record shape. These checks establish whether a
schema-valid manifest is actually ready to authorize opening an untouched
sealed expert-validation set. The audit intentionally contains no statistical
acceptance threshold; those values remain pilot-derived and preregistered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ZERO_SHA256 = "0" * 64
_REQUIRED_DEPENDENCY_PURPOSES = frozenset(
    {"terminology", "ucum", "fhir_validation", "hl7v2_validation"}
)
_REQUIRED_REVIEW_ROLES = frozenset(
    {
        "primary_reviewer_interoperability",
        "primary_reviewer_clinical_informatics",
        "adjudicator",
        "data_custodian",
    }
)
_BLINDING_FLAGS = (
    "model_identity_hidden",
    "generation_strategy_hidden",
    "verifier_verdict_hidden",
    "claimed_provenance_hidden",
    "other_reviewer_labels_hidden",
)
_PLACEHOLDER_TOKENS = (
    "TO_BE_FROZEN",
    "TO-BE-FROZEN",
    "TO_BE_ASSIGNED",
    "TO-BE-ASSIGNED",
)


@dataclass(frozen=True)
class FreezeReadinessReport:
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready_to_open_sealed_set(self) -> bool:
        return not self.blockers


def _contains_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zeroish_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and set(value.lower()) <= {"0"}


def _artifact_blockers(
    components: dict[str, Any],
    blockers: list[str],
) -> None:
    for component_name, component in sorted(components.items()):
        if not isinstance(component, dict):
            blockers.append(f"component {component_name} is not an object")
            continue
        version = component.get("version")
        path_or_ref = component.get("path_or_ref")
        digest = component.get("sha256")
        if _contains_placeholder(version) or _contains_placeholder(path_or_ref):
            blockers.append(f"component {component_name} still contains freeze placeholders")
        if digest == _ZERO_SHA256:
            blockers.append(f"component {component_name} still uses the zero placeholder hash")


def assess_presealed_freeze(manifest: dict[str, Any]) -> FreezeReadinessReport:
    """Return blockers/warnings before an untouched sealed set may be opened.

    The input is expected to have passed ``freeze_manifest.schema.json`` first.
    This function deliberately refuses to infer missing governance facts.
    """

    blockers: list[str] = []
    warnings: list[str] = []

    if _contains_placeholder(manifest.get("manifest_id")):
        blockers.append("manifest_id is still a placeholder")
    if manifest.get("freeze_complete") is not True:
        blockers.append("freeze_complete is not true")
    if manifest.get("freeze_timestamp") is None:
        blockers.append("freeze_timestamp is not recorded")
    if _contains_placeholder(manifest.get("protocol_version")):
        blockers.append("protocol_version is still a placeholder")
    if _zeroish_hex(manifest.get("repository_commit")):
        blockers.append("repository_commit is still a zero placeholder")

    _artifact_blockers(
        {
            "instrument_component_manifest": manifest.get(
                "instrument_component_manifest"
            )
        },
        blockers,
    )
    _artifact_blockers(manifest.get("instrument_components", {}), blockers)
    _artifact_blockers(
        {
            "reviewer_roster": manifest.get("reviewer_roster"),
            "case_assignment_manifest": manifest.get(
                "case_assignment_manifest"
            ),
            "analysis_preregistration": manifest.get(
                "analysis_preregistration"
            ),
            "sample_size_preregistration": manifest.get(
                "sample_size_preregistration"
            ),
            "model_prompt_configuration": manifest.get(
                "model_prompt_configuration"
            ),
        },
        blockers,
    )

    dependency_purposes = {
        dependency.get("purpose")
        for dependency in manifest.get("dependencies", [])
        if isinstance(dependency, dict)
    }
    missing_dependencies = _REQUIRED_DEPENDENCY_PURPOSES - dependency_purposes
    if missing_dependencies:
        blockers.append(
            "measurement-critical dependencies are not pinned for: "
            + ", ".join(sorted(missing_dependencies))
        )

    for dependency in manifest.get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        purpose = dependency.get("purpose")
        if purpose not in _REQUIRED_DEPENDENCY_PURPOSES:
            continue
        name = dependency.get("name", "unknown")
        if _contains_placeholder(dependency.get("version")):
            blockers.append(
                f"measurement-critical dependency {name} has placeholder version"
            )
        if _contains_placeholder(dependency.get("source_or_ref")):
            blockers.append(
                f"measurement-critical dependency {name} has placeholder source"
            )
        digest = dependency.get("sha256")
        if digest is None or _zeroish_hex(digest):
            blockers.append(
                f"measurement-critical dependency {name} lacks a frozen SHA-256"
            )

    sealed_set = manifest.get("sealed_set", {})
    if sealed_set.get("split") != "sealed_test":
        blockers.append("confirmatory freeze manifest must identify split as sealed_test")
    if _contains_placeholder(sealed_set.get("bundle_id")):
        blockers.append("sealed-set bundle_id is still a placeholder")
    if sealed_set.get("case_count", 0) <= 0:
        blockers.append("sealed-set case_count must be positive before opening")
    if sealed_set.get("bundle_sha256") == _ZERO_SHA256:
        blockers.append("sealed-set bundle still uses the zero placeholder hash")
    if sealed_set.get("case_manifest_sha256") == _ZERO_SHA256:
        blockers.append("sealed-set case manifest still uses the zero placeholder hash")
    if sealed_set.get("opened") is True:
        blockers.append("sealed set is already marked opened; this is not a pre-opening freeze")
    if sealed_set.get("opened_at") is not None:
        blockers.append("opened_at must be null before first sealed-set opening")
    if sealed_set.get("opened_by_role_ids"):
        blockers.append("opened_by_role_ids must be empty before first sealed-set opening")

    blinding = manifest.get("blinding", {})
    if blinding.get("controls_verified") is not True:
        blockers.append("blinding controls have not been verified")
    for flag in _BLINDING_FLAGS:
        if blinding.get(flag) is not True:
            blockers.append(f"required blinding control is not enabled: {flag}")

    present_roles = {
        item.get("role")
        for item in blinding.get("role_ids", [])
        if isinstance(item, dict)
    }
    missing_roles = _REQUIRED_REVIEW_ROLES - present_roles
    if missing_roles:
        blockers.append(
            "required blinded-validation roles are not assigned: "
            + ", ".join(sorted(missing_roles))
        )

    acceptance_gate = manifest.get("acceptance_gate")
    if not isinstance(acceptance_gate, dict):
        blockers.append("pilot-derived acceptance gate has not been preregistered")
    else:
        if acceptance_gate.get("defined_before_sealed_opening") is not True:
            blockers.append(
                "acceptance gate is not attested as defined before sealed opening"
            )
        if _contains_placeholder(acceptance_gate.get("preregistration_ref")):
            blockers.append("acceptance gate preregistration_ref is still a placeholder")
        if _zeroish_hex(acceptance_gate.get("preregistration_sha256")):
            blockers.append(
                "acceptance gate preregistration_sha256 is still a zero placeholder"
            )
        if _contains_placeholder(acceptance_gate.get("gate_policy_summary")):
            blockers.append("acceptance gate policy summary is still a placeholder")

    for amendment in manifest.get("post_freeze_amendments", []):
        if not isinstance(amendment, dict):
            continue
        if amendment.get("sealed_set_had_been_opened") is not True:
            warnings.append(
                f"pre-opening amendment recorded: {amendment.get('amendment_id', 'unknown')}"
            )
            continue
        disposition = amendment.get("disposition")
        if disposition == "REQUIRES_NEW_SEALED_SET":
            blockers.append(
                "post-unsealing instrument amendment requires a fresh untouched sealed set: "
                + str(amendment.get("amendment_id", "unknown"))
            )
        elif disposition == "DOWNGRADE_TO_EXPLORATORY":
            blockers.append(
                "post-unsealing amendment downgrades the analysis to exploratory: "
                + str(amendment.get("amendment_id", "unknown"))
            )

    return FreezeReadinessReport(
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )
