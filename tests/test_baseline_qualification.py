import yaml

from fhirbridge.baseline_qualification import assess_baseline_qualification

_TEMPLATE = "models/examples/baseline_qualification_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready() -> dict:
    document = _template()
    document["qualification_id"] = "BASELINE-QUAL-001"
    document["status"] = "qualified"
    document["created_at"] = "2026-10-20T20:00:00Z"
    document["repository_commit"] = "abcdef1"
    document["contract"]["sha256"] = "1" * 64
    document["target_profile"]["profile_bundle_sha256"] = "2" * 64
    document["target_profile"]["qualification_report_sha256"] = "3" * 64
    document["renderer_component"]["sha256"] = "4" * 64
    for index, item in enumerate(document["primary_family_evidence"], start=1):
        item["validation_record_sha256"] = f"{index:x}" * 64
    return document


def test_repository_baseline_template_is_deliberately_not_ready() -> None:
    readiness = assess_baseline_qualification(_template())

    assert not readiness.ready
    assert any("not marked qualified" in item for item in readiness.blockers)
    assert any("placeholder" in item for item in readiness.blockers)
    assert any("SHA-256" in item for item in readiness.blockers)


def test_complete_eleven_family_baseline_qualification_can_be_ready() -> None:
    readiness = assess_baseline_qualification(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_baseline_qualification_requires_every_primary_family_once() -> None:
    document = _ready()
    document["primary_family_evidence"][-1]["template_id"] = "LAB-010"

    readiness = assess_baseline_qualification(document)

    assert not readiness.ready
    assert any("duplicate baseline family evidence" in item for item in readiness.blockers)
    assert any("LAB-011" in item for item in readiness.blockers)


def test_baseline_qualification_rejects_unfaithful_family() -> None:
    document = _ready()
    document["primary_family_evidence"][3]["semantic_verdict"] = "UNFAITHFUL"

    readiness = assess_baseline_qualification(document)

    assert not readiness.ready
    assert any("semantic verdict is not FAITHFUL" in item for item in readiness.blockers)


def test_baseline_qualification_rejects_placeholder_profile_hash() -> None:
    document = _ready()
    document["target_profile"]["profile_bundle_sha256"] = "0" * 64

    readiness = assess_baseline_qualification(document)

    assert not readiness.ready
    assert any("profile_bundle_sha256" in item for item in readiness.blockers)
