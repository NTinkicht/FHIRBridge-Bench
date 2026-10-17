"""Development-only eleven-family readiness evidence for Path B.

This module exercises synthetic canonical -> FHIR -> canonical development
round trips and the *guarded* HL7 v2 order-context renderer. It does not
evaluate complete Edition 5 conformance, independent validator accuracy,
external FHIR validation, or sealed/confirmatory outcomes.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.verifier
from fhirbridge.schema_validation import load_yaml

_SCENARIOS = Path("benchmark/scenarios/lab_core_v0.1.yaml")
_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_FREEZE = Path("benchmark/protocol_freeze_gates.yaml")
_REQUIRED_FAMILIES = tuple(f"LAB-{index:03d}" for index in range(1, 12))
_FATAL = frozenset({"FABRICATION", "CORRUPTION", "OMISSION", "MISATTRIBUTION"})


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _check_prefreeze_boundaries(
    contract: dict[str, Any],
    freeze: dict[str, Any],
) -> None:
    header = contract.get("contract", {})
    target = contract.get("target", {})
    decision = freeze.get("protocol_freeze", {}).get("development_path_decision", {})
    if (
        header.get("freeze_status") != "not_frozen"
        or target.get("selected_validation_route")
        != "bounded_PDF_derived_Path_B_pending_independent_qualification"
        or target.get("bounded_G1_qualification_complete") is not False
        or target.get("confirmatory_inference_authorized") is not False
        or freeze.get("protocol_freeze", {}).get("status") != "blocked"
        or decision.get("selected") != "bounded_independent_reconstruction"
        or decision.get("gated_qualification_alternative_implemented") is not False
        or decision.get("confirmatory_permission") is not False
    ):
        raise ValueError(
            "development-only feasibility runner refuses a changed/unfrozen "
            "qualification boundary; do not repurpose it for confirmatory use"
        )


def _primary_families(spec: dict[str, Any]) -> list[dict[str, Any]]:
    families = spec.get("scenario_families")
    if not isinstance(families, list):
        raise ValueError("scenario specification is missing its family list")
    selected = [
        family
        for family in families
        if isinstance(family, dict) and family.get("primary_endpoint_eligible") is True
    ]
    ids = [family.get("id") for family in selected]
    if (
        len(ids) != 11
        or len(set(ids)) != 11
        or set(ids) != set(_REQUIRED_FAMILIES)
    ):
        raise ValueError("expected exactly LAB-001 through LAB-011 primary families")
    for family in selected:
        if "order_context" not in family.get("required_fact_groups", []):
            raise ValueError(f"order context not declared for {family['id']}")
    return sorted(selected, key=lambda family: family["id"])


def _inspect_one(
    template_id: str,
    seed: int,
    contract: dict[str, Any],
    policy: Any,
) -> dict[str, Any]:
    graph = fhirbridge.canonical.generate_lab_scenario(
        template_id,
        seed,
        include_order_context=True,
        partition="development",
    )
    if graph.get("scenario_metadata", {}).get("primary_endpoint_eligible") is not True:
        raise ValueError(f"{template_id} unexpectedly not designated primary")
    facts = graph["facts"]
    orders = [fact for fact in facts if fact.get("fact_type") == "order"]
    reports = [
        fact for fact in facts if fact.get("fact_type") == "diagnostic_report"
    ]
    if len(orders) != 1 or len(reports) != 1:
        raise ValueError(f"{template_id} lacks exactly one authored order/report")
    if not orders[0].get("identifiers"):
        raise ValueError(f"{template_id} lacks a source-authored order identifier")

    rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
        graph, contract=contract
    )
    artifact = rendered.artifact
    if not isinstance(artifact, dict) or not isinstance(artifact.get("entry"), list):
        raise ValueError(f"{template_id} failed to produce a FHIR Bundle")
    resources = [
        entry.get("resource")
        for entry in artifact["entry"]
        if isinstance(entry, dict)
    ]
    requests = [
        res for res in resources
        if isinstance(res, dict) and res.get("resourceType") == "ServiceRequest"
    ]
    report_resources = [
        res for res in resources
        if isinstance(res, dict) and res.get("resourceType") == "DiagnosticReport"
    ]
    if len(requests) != 1 or len(report_resources) != 1:
        raise ValueError(f"{template_id} FHIR lacks exactly one order/report")
    if report_resources[0].get("basedOn") != [
        {"reference": f"ServiceRequest/{requests[0]['id']}"}
    ]:
        raise ValueError(f"{template_id} lost the source-authored order relation")

    lifted = fhirbridge.lifters.FhirR4LabLifter().lift(
        artifact, artifact_id=f"{template_id}-{seed}-path-b-dev"
    )
    result = fhirbridge.verifier.classify_graph(
        facts, list(lifted.facts), policy=policy
    )
    failures = [
        decision.classification
        for decision in result.decisions
        if decision.primary_endpoint_eligible
        and decision.classification in _FATAL
    ]
    if result.primary_endpoint_verdict != "FAITHFUL" or failures:
        raise ValueError(f"{template_id} has draft-policy FHIR round-trip failures")

    # Unlike the draft FHIR representation, the HL7 v2 order serializer has
    # not been qualified against independently extracted Edition 5 rules.
    # A successful HL7 return here would be a guard regression, NOT progress.
    try:
        fhirbridge.renderers.Hl7V251OruRendererA().render(
            graph, contract=contract
        )
    except ValueError as exc:
        if (
            "order-context rendering is fail-closed" not in str(exc)
            or "independent Path B" not in str(exc)
        ):
            raise ValueError(
                f"{template_id} raised an unexpected HL7 rendering error"
            ) from exc
    else:
        raise ValueError(
            f"{template_id} HL7 order renderer unexpectedly bypassed its G1 guard"
        )

    return {
        "family_id": template_id,
        "seed": seed,
        "source_order_fact_present": True,
        "fhir_service_request_and_based_on_present": True,
        "fhir_development_roundtrip": "FAITHFUL_UNDER_DRAFT_POLICY_ONLY",
        "hl7v2_order_context_serialization": "BLOCKED_FAIL_CLOSED",
        "hl7v2_edition5_bounded_g1_status": "NOT_QUALIFIED",
        "external_fhir_validator_checked_by_this_report": False,
        "independent_standards_review_received": False,
        "confirmatory_evidence": False,
    }


def build_development_feasibility(
    *,
    scenario_path: Path = _SCENARIOS,
    contract_path: Path = _CONTRACT,
    freeze_path: Path = _FREEZE,
) -> dict[str, Any]:
    """Reproducible development census; stop rather than mask any abnormal case."""

    spec = load_yaml(scenario_path)
    contract = load_yaml(contract_path)
    freeze = load_yaml(freeze_path)
    _check_prefreeze_boundaries(contract, freeze)
    families = _primary_families(spec)
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    rows = [
        _inspect_one(
            family["id"],
            seed=9490 + int(family["id"].split("-")[1]),
            contract=contract,
            policy=policy,
        )
        for family in families
    ]
    if len(rows) != 11:
        raise ValueError("eleven-family development census incomplete")
    return {
        "report_id": "PATH-B-ELEVEN-FAMILY-PREFREEZE-DEVELOPMENT",
        "status": "PREFREEZE_NOT_SCIENTIFICALLY_QUALIFIED",
        "scientific_role": "development_feasibility_only",
        "input_sha256": {
            "scenario_specification": _sha256_file(scenario_path),
            "draft_contract": _sha256_file(contract_path),
            "protocol_freeze_gates": _sha256_file(freeze_path),
        },
        "primary_family_count": len(rows),
        "development_fhir_roundtrip_draft_faithful_count": len(rows),
        "hl7v2_order_renderer_fail_closed_count": len(rows),
        "independent_G1_qualified_family_count": 0,
        "external_fhir_validation_performed_here": False,
        "source_completeness_denominator_established": False,
        "confirmatory_permission": False,
        "sealed_set_opened": False,
        "rows": rows,
    }
