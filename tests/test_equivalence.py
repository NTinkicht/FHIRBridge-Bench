import pytest

from fhirbridge.verifier import (
    ExactTerminologyEquivalence,
    ExactUnitEquivalence,
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
