import fhirbridge.schema_validation
from fhirbridge.fault_batch import (
    build_development_fault_batch,
    class_counts,
)

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _contract() -> dict:
    return fhirbridge.schema_validation.load_yaml(_CONTRACT)


def test_development_fault_batch_meets_pre_freeze_count_targets() -> None:
    batch = build_development_fault_batch(_contract())
    counts = class_counts(batch)

    assert counts["FABRICATION"] == 50
    assert counts["OMISSION"] == 50
    assert counts["MISATTRIBUTION"] == 50
    assert counts["CORRUPTION"] == 64
    assert counts["MULTI_FAULT"] == 100
    assert len(batch.cases) == 314


def test_development_fault_batch_is_deterministic() -> None:
    first = build_development_fault_batch(_contract(), seed_base=13000)
    second = build_development_fault_batch(_contract(), seed_base=13000)

    assert first.batch_sha256 == second.batch_sha256
    assert first.to_dict() == second.to_dict()


def test_fault_batch_records_deterministic_manifest_and_graph_hashes() -> None:
    batch = build_development_fault_batch(_contract())

    assert all(len(case.graph_sha256) == 64 for case in batch.cases)
    assert all(
        len(case.manifest["manifest_sha256"]) == 64
        for case in batch.cases
    )
    assert all(
        case.manifest["contract_version"] == "0.2.0"
        for case in batch.cases
    )


def test_multi_fault_batch_cycles_all_three_composed_templates() -> None:
    batch = build_development_fault_batch(_contract())
    multi_fault_ids = {
        case.fault_id
        for case in batch.cases
        if case.semantic_class == "MULTI_FAULT"
    }

    assert multi_fault_ids == {"MF001", "MF002", "MF003"}


def test_mf003_batch_cases_use_panel_topology() -> None:
    batch = build_development_fault_batch(_contract())

    mf003_cases = [
        case
        for case in batch.cases
        if case.semantic_class == "MULTI_FAULT" and case.fault_id == "MF003"
    ]

    assert mf003_cases
    assert all(case.scenario_id == "LAB-005" for case in mf003_cases)
