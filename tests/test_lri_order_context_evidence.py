import yaml

_PATH = "benchmark/lri_order_context_evidence.yaml"


def _record() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_lri_order_context_remains_unresolved_until_exact_edition5_profile() -> None:
    record = _record()

    assert (
        record["evidence_record"]["decision_status"]
        == "unresolved_until_exact_edition5_profile"
    )
    assert record["freeze_decision"]["exact_edition5_profile_bundle_required"] is True


def test_legacy_and_local_sources_cannot_define_confirmatory_order_semantics() -> None:
    record = _record()

    assert record["legacy_nist_comparator"]["role"] == "historical_differential_only"
    assert (
        record["secondary_implementation_evidence"]["role"]
        == "corroborating_secondary_only"
    )
    prohibited = set(record["freeze_decision"]["prohibited_shortcuts"])
    assert "infer_edition5_from_legacy_r2" in prohibited
    assert "infer_edition5_from_michigan_local_profile" in prohibited
    assert "invent_order_identifiers_to_make_validator_green" in prohibited


def test_safe_order_context_path_preserves_source_grounding_boundary() -> None:
    record = _record()

    text = record["freeze_decision"]["safe_if_order_context_required"]
    assert "canonical order fact" in text
    assert "ServiceRequest" in text
    assert "ORC/OBR" in text
    assert "outside the primary endpoint" in text
