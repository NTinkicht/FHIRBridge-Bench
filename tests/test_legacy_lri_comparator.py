import yaml

_PATH = "benchmark/hl7v2_legacy_lri_comparator.yaml"


def _record() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_legacy_lri_profile_can_never_be_promoted_to_confirmatory_truth() -> None:
    record = _record()

    assert record["comparator"]["status"] == "legacy_differential_only"
    assert record["comparator"]["used_as_ground_truth"] is False
    assert record["comparator"]["confirmatory_eligible"] is False
    assert "never_use_as_edition5_profile" in record["safeguards"]
    assert "exact_edition5_profile_bundle_still_required" in record["safeguards"]


def test_legacy_lri_profile_provenance_is_pinned() -> None:
    record = _record()
    source = record["source"]

    assert (
        source["repository_commit"]
        == "3ee9df7d3345944f4a70cccf9be504e499a24c1b"
    )
    assert (
        source["profile_git_blob_sha"]
        == "5b1dd8d674a255e68f3563bcb685023937d776b2"
    )
    assert (
        source["constraints_git_blob_sha"]
        == "ba5605fd90f75790846b7d185ab2f0c13db3fb4c"
    )


def test_legacy_profile_order_requirements_are_recorded_as_non_authoritative() -> None:
    record = _record()

    assert record["observed_structure"]["orc_usage_in_legacy_profile"] == "required"
    assert record["observed_structure"]["obr_usage_in_legacy_profile"] == "required"
    assert (
        record["profile_metadata"]["constraints_metadata_name"]
        == "LRI R2 conformance context"
    )
