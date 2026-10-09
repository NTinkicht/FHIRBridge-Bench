from copy import deepcopy

from fhirbridge.renderer_b_submission import assess_renderer_b_declaration


def _declaration() -> dict:
    return {
        "schema_version": "0.1.0",
        "renderer_id": "RENDERER-B",
        "renderer_version": "0.1.0",
        "contributor": {
            "identity": "EXT-RB-01",
            "role": "independent_renderer_b_implementer",
            "organization": None,
        },
        "implementation": {
            "language": "Java 17",
            "major_libraries": ["HAPI"],
            "source_commit": "1234567890abcdef1234567890abcdef12345678",
            "implementation_notes": None,
        },
        "contract": {
            "contract_id": "F2V-LAB-ORU-R01-001",
            "contract_version": "0.2.0",
        },
        "standards_sources": [
            {
                "name": "HL7 FHIR R4",
                "version_or_date": "R4",
                "reference": None,
            },
            {
                "name": "HL7 v2.5.1 Laboratory Results Interface (LRI)",
                "version_or_date": "Edition 5",
                "reference": None,
            },
        ],
        "implementation_period": {
            "started_on": "2026-10-10",
            "completed_on": "2026-10-11",
        },
        "independence": {
            "renderer_a_source_inspected_before_initial_commit": False,
            "renderer_a_outputs_inspected_before_initial_commit": False,
            "renderer_a_mapping_code_reused": False,
            "llm_generated_mapping_code_used": False,
            "shared_semantic_mapping_utility_used": False,
            "accidental_exposure": None,
            "same_language_as_renderer_a_rationale": None,
            "declaration_complete": True,
        },
        "terminology_dependencies": [],
        "known_unsupported_cases": ["LAB-012 remains explicitly indeterminate"],
        "signed_statement": "I attest to the structured declaration above.",
    }


def test_complete_independent_declaration_is_ready() -> None:
    readiness = assess_renderer_b_declaration(_declaration())

    assert readiness.ready_for_differential_comparison is True
    assert readiness.blockers == ()
    assert readiness.warnings == ()


def test_renderer_a_exposure_blocks_comparison() -> None:
    declaration = _declaration()
    declaration["independence"][
        "renderer_a_source_inspected_before_initial_commit"
    ] = True

    readiness = assess_renderer_b_declaration(declaration)

    assert readiness.ready_for_differential_comparison is False
    assert any(
        "renderer_a_source_inspected_before_initial_commit" in blocker
        for blocker in readiness.blockers
    )


def test_python_requires_same_language_independence_rationale() -> None:
    declaration = _declaration()
    declaration["implementation"]["language"] = "Python 3.11"

    blocked = assess_renderer_b_declaration(declaration)
    assert blocked.ready_for_differential_comparison is False
    assert any("same-language" in blocker for blocker in blocked.blockers)

    declaration["independence"]["same_language_as_renderer_a_rationale"] = (
        "Independently authored with a different standards library and no "
        "shared mapping or serialization utilities."
    )
    ready = assess_renderer_b_declaration(declaration)
    assert ready.ready_for_differential_comparison is True


def test_llm_mapping_use_is_audit_warning_not_automatic_failure() -> None:
    declaration = _declaration()
    declaration["independence"]["llm_generated_mapping_code_used"] = True

    readiness = assess_renderer_b_declaration(declaration)

    assert readiness.ready_for_differential_comparison is True
    assert len(readiness.warnings) == 1
    assert "prompt/context provenance" in readiness.warnings[0]


def test_placeholders_block_comparison() -> None:
    declaration = deepcopy(_declaration())
    declaration["contributor"]["identity"] = (
        "TO_BE_COMPLETED_BY_INDEPENDENT_IMPLEMENTER"
    )
    declaration["known_unsupported_cases"] = [
        "TO_BE_COMPLETED_BY_INDEPENDENT_IMPLEMENTER"
    ]

    readiness = assess_renderer_b_declaration(declaration)

    assert readiness.ready_for_differential_comparison is False
    assert len(readiness.blockers) >= 2
