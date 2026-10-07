import pytest

from fhirbridge.verifier import (
    ExactTerminologyEquivalence,
    ExactUnitEquivalence,
    FrozenMappingTerminologyEquivalence,
    identifiers_equivalent,
    instants_equivalent,
)


def test_exact_terminology_equivalence_requires_system_and_code() -> None:
    provider = ExactTerminologyEquivalence()
    same = provider.equivalent("http://loinc.org", "2345-7", "http://loinc.org", "2345-7")
    different = provider.equivalent(
        "http://loinc.org",
        "2345-7",
        "http://loinc.org",
        "2951-2",
    )

    assert same.equivalent is True
    assert same.rationale_code == "EXACT_CODE_MATCH"
    assert different.equivalent is False
    assert different.rationale_code == "CODE_MISMATCH"


def test_identifier_namespace_is_part_of_identity() -> None:
    source = {"system": "urn:a", "value": "123"}
    target = {"system": "urn:b", "value": "123"}

    strict = identifiers_equivalent(source, target)
    declared = identifiers_equivalent(source, target, allow_namespace_change=True)

    assert strict.equivalent is False
    assert strict.rationale_code == "IDENTIFIER_NAMESPACE_MISMATCH"
    assert declared.equivalent is True
    assert declared.rationale_code == "DECLARED_IDENTIFIER_NAMESPACE_CHANGE"


def test_exact_unit_provider_compares_value_and_unit_jointly() -> None:
    provider = ExactUnitEquivalence()
    same = provider.equivalent(92.0, "mg/dL", 92.0, "mg/dL")
    wrong_unit = provider.equivalent(92.0, "mg/dL", 92.0, "mmol/L")
    wrong_value = provider.equivalent(92.0, "mg/dL", 93.0, "mg/dL")

    assert same.equivalent is True
    assert wrong_unit.equivalent is False
    assert wrong_value.equivalent is False


def test_instant_equivalence_normalizes_timezone_offsets() -> None:
    same = instants_equivalent(
        "2026-09-20T08:15:00+04:00",
        "2026-09-20T04:15:00Z",
    )
    different = instants_equivalent(
        "2026-09-20T08:15:00+04:00",
        "2026-09-20T04:16:00Z",
    )

    assert same.equivalent is True
    assert same.rationale_code == "SAME_INSTANT"
    assert different.equivalent is False


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone required"):
        instants_equivalent("2026-09-20T08:15:00", "2026-09-20T04:15:00Z")


def test_frozen_mapping_provider_accepts_only_explicit_directional_mapping() -> None:
    provider = FrozenMappingTerminologyEquivalence(
        {
            (
                "urn:local:lab",
                "GLU",
                "http://loinc.org",
                "2345-7",
            )
        },
        mapping_id="TEST-CONCEPTMAP",
        mapping_version="1.0.0",
    )

    approved = provider.equivalent(
        "urn:local:lab",
        "GLU",
        "http://loinc.org",
        "2345-7",
    )
    reverse = provider.equivalent(
        "http://loinc.org",
        "2345-7",
        "urn:local:lab",
        "GLU",
    )
    unrelated = provider.equivalent(
        "urn:local:lab",
        "GLU",
        "http://loinc.org",
        "2951-2",
    )

    assert approved.equivalent is True
    assert approved.rationale_code == "FROZEN_APPROVED_CODE_MAPPING"
    assert approved.details["mapping_id"] == "TEST-CONCEPTMAP"
    assert reverse.equivalent is False
    assert unrelated.equivalent is False


def test_frozen_mapping_provider_retains_exact_identity_without_mapping_entry() -> None:
    provider = FrozenMappingTerminologyEquivalence(
        set(),
        mapping_id="EMPTY-MAP",
        mapping_version="1.0.0",
    )

    result = provider.equivalent(
        "http://loinc.org",
        "2345-7",
        "http://loinc.org",
        "2345-7",
    )

    assert result.equivalent is True
    assert result.rationale_code == "EXACT_CODE_MATCH"


def test_frozen_mapping_provider_rejects_missing_mapping_identity() -> None:
    with pytest.raises(ValueError, match="mapping_id"):
        FrozenMappingTerminologyEquivalence(
            set(),
            mapping_id="",
            mapping_version="1.0.0",
        )
