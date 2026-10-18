import yaml

from fhirbridge.primary_vur_hypothesis import (
    assess_primary_vur_hypothesis,
)

_TEMPLATE = (
    "analysis/examples/primary_vur_hypothesis_preregistration_template.yaml"
)


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready() -> dict:
    document = _template()
    document["record_id"] = "PRIMARY-VUR-001"
    document["status"] = "preregistered"
    document["created_at"] = "2026-10-20T16:00:00Z"
    document["pilot_evidence"].update(
        {
            "pilot_case_manifest_sha256": "1" * 64,
            "pilot_analysis_sha256": "2" * 64,
        }
    )
    document["hypothesis"]["nontrivial_vur_threshold"] = 0.10
    document["hypothesis"]["threshold_rationale"] = (
        "Pilot-derived non-trivial semantic-error threshold."
    )
    document["target_population"].update(
        {
            "inclusion_rule": (
                "Frozen FHIR-to-HL7v2 LLM transformations eligible for the "
                "primary VUR estimand."
            ),
            "model_strategy_aggregation_policy": (
                "Preregistered cluster-aware aggregation across frozen "
                "model/strategy rows."
            ),
        }
    )
    document["inference"].update(
        {
            "method": "cluster_aware_one_sided_threshold_test",
            "cluster_handling": (
                "Use frozen analysis_cluster_id without post-run regrouping."
            ),
            "confidence_interval_method": (
                "Preregistered cluster-aware one-sided 95% interval."
            ),
            "decision_rule": (
                "Reject H0 only under the frozen method at alpha 0.05."
            ),
        }
    )
    return document


def test_repository_primary_hypothesis_template_is_not_ready() -> None:
    readiness = assess_primary_vur_hypothesis(_template())

    assert not readiness.ready
    assert any("not marked preregistered" in item for item in readiness.blockers)
    assert any("zero placeholder" in item for item in readiness.blockers)
    assert any("threshold rationale" in item for item in readiness.blockers)
    assert any("aggregation_policy" in item for item in readiness.blockers)


def test_complete_primary_hypothesis_record_can_be_ready() -> None:
    readiness = assess_primary_vur_hypothesis(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_primary_hypothesis_rejects_zero_threshold() -> None:
    document = _ready()
    document["hypothesis"]["nontrivial_vur_threshold"] = 0.0

    readiness = assess_primary_vur_hypothesis(document)

    assert not readiness.ready
    assert any("threshold must be numeric in (0,1)" in item for item in readiness.blockers)


def test_primary_hypothesis_rejects_postrun_cluster_field() -> None:
    document = _ready()
    document["target_population"]["cluster_id_field"] = "post_run_cluster"

    readiness = assess_primary_vur_hypothesis(document)

    assert not readiness.ready
    assert any("analysis_cluster_id" in item for item in readiness.blockers)
