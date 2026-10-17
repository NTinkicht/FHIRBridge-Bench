import yaml

_PATH = "benchmark/lri_errata_watch.yaml"


def _doc() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)["errata_watch"]


def test_secondary_5_1_report_does_not_silently_change_target() -> None:
    document = _doc()

    assert document["status"] == (
        "unresolved_secondary_report_no_target_change"
    )
    assert document["current_official_product"]["target_disposition"] == (
        "remains_current_benchmark_publication_target"
    )
    assert document["secondary_report"][
        "official_HL7_product_or_artifact_located"
    ] is False
    assert document["benchmark_relevance"][
        "immediate_protocol_change_required"
    ] is False


def test_machine_bundle_must_be_checked_for_post_2024dec_revision() -> None:
    requirements = set(_doc()["acquisition_requirements"])

    assert (
        "ask_artifact_provider_whether_any_post_2024DEC_official_errata_bundle_exists"
        in requirements
    )
    assert (
        "record_exact_profile_component_versions_from_received_machine_bundle"
        in requirements
    )
