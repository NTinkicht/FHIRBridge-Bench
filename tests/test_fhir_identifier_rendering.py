from fhirbridge.renderers.fhir_r4_a import _identifier


def test_medical_record_identifier_keeps_valid_r4_identifier_type_code() -> None:
    rendered = _identifier(
        {
            "system": "urn:test:mrn",
            "value": "MRN-1",
            "type": "MR",
        }
    )

    assert rendered["type"]["text"] == "MR"
    assert rendered["type"]["coding"] == [
        {
            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
            "code": "MR",
        }
    ]


def test_patient_internal_identifier_does_not_assert_invalid_r4_type_code() -> None:
    rendered = _identifier(
        {
            "system": "urn:test:alternate",
            "value": "ALT-1",
            "type": "PI",
        }
    )

    assert rendered["type"] == {"text": "PI"}
    assert rendered["value"] == "ALT-1"
    assert rendered["system"] == "urn:test:alternate"


def test_unknown_identifier_type_is_not_projected_without_review() -> None:
    rendered = _identifier(
        {
            "system": "urn:test:other",
            "value": "X-1",
            "type": "LOCAL-TYPE",
        }
    )

    assert "type" not in rendered
