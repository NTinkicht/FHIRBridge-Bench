from copy import deepcopy

import pytest
import yaml

from fhirbridge.freeze_dependencies import build_freeze_dependencies

_TOOLING = "benchmark/tooling_versions.yaml"


def _tooling() -> dict:
    with open(_TOOLING, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _frozen_tooling() -> dict:
    document = deepcopy(_tooling())
    document["manifest"]["status"] = "frozen"
    v2 = document["structural_validation"]["hl7v2"]
    v2["profile_artifact"] = "qualification/hl7v2/lri-ed5-bundle"
    v2["profile_artifact_sha256"] = "a" * 64
    v2["profile_validation_qualification_passed"] = True
    return document


def test_current_candidate_tooling_cannot_produce_freeze_dependencies() -> None:
    with pytest.raises(ValueError):
        build_freeze_dependencies(_tooling())


def test_frozen_tooling_derives_all_required_dependency_purposes() -> None:
    dependencies = build_freeze_dependencies(_frozen_tooling())

    purposes = {item["purpose"] for item in dependencies}
    assert {"terminology", "ucum", "fhir_validation", "hl7v2_validation"} <= purposes
    assert len(dependencies) == 6
    assert all(len(item["sha256"]) == 64 for item in dependencies)


def test_hl7v2_dependency_binds_profile_and_validator_source() -> None:
    dependency = next(
        item
        for item in build_freeze_dependencies(_frozen_tooling())
        if item["purpose"] == "hl7v2_validation"
    )

    assert dependency["sha256"] == "a" * 64
    assert "LRI_Ed5" in dependency["version"]
    assert "validator=1.5.0" in dependency["version"]
    assert "eeac90c5f88dca3018992005232acdf3da644d88" in dependency["source_or_ref"]


def test_dependency_builder_rejects_missing_measurement_pin() -> None:
    document = _frozen_tooling()
    document["terminology"]["loinc"]["local_snapshot_sha256"] = ""

    with pytest.raises(ValueError):
        build_freeze_dependencies(document)
