from copy import deepcopy

from fhirbridge.renderer_b_submission import assess_renderer_b_declaration


def _declaration() -> dict:
    return {
        "schema_version": "0.2.0",
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
        "clean_room_inputs": {
            "repository_full_name": "NTinkicht/FHIRBridge-Bench",
            "branch": "renderer-b-cleanroom",
            "starting_commit": "1" * 40,
            "challenge_id": "FHIRBRIDGE-RENDERER-B-DEV-001",
            "challenge_version": "0.3.0",
            "challenge_manifest_sha256": "2" * 64,
            "contract_path": "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml",
            "contract_sha256": "3" * 64,
        },
        "contract": {
            "contract_id": "F2V-LAB-ORU-R01-001",
            "contract_version": "0.3.0",
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


def _expected_inputs() -> dict:
    return dict(_declaration()["clean_room_inputs"])


def test_complete_independent_declaration_is_ready() -> None:
    readiness = assess_renderer_b_declaration(
        _declaration(),
        expected_clean_room_inputs=_expected_inputs(),
    )

    assert readiness.ready_for_differential_comparison is True
    assert readiness.blockers == ()
    assert readiness.warnings == ()


def test_renderer_a_exposure_blocks_comparison() -> None:
    declaration = _declaration()
    declaration["independence"][
        "renderer_a_source_inspected_before_initial_commit"
    ] = True

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )

    assert readiness.ready_for_differential_comparison is False
    assert any(
        "renderer_a_source_inspected_before_initial_commit" in blocker
        for blocker in readiness.blockers
    )


def test_python_requires_same_language_independence_rationale() -> None:
    declaration = _declaration()
    declaration["implementation"]["language"] = "Python 3.11"

    blocked = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )
    assert blocked.ready_for_differential_comparison is False
    assert any("same-language" in blocker for blocker in blocked.blockers)

    declaration["independence"]["same_language_as_renderer_a_rationale"] = (
        "Independently authored with a different standards library and no "
        "shared mapping or serialization utilities."
    )
    ready = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )
    assert ready.ready_for_differential_comparison is True


def test_codex_mapping_use_blocks_scientific_gate_but_allows_exploratory_check() -> None:
    declaration = _declaration()
    declaration["contributor"]["identity"] = "CODEX-AGENT-B"
    declaration["independence"]["llm_generated_mapping_code_used"] = True

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )

    assert readiness.ready_for_differential_comparison is False
    assert readiness.ready_for_exploratory_agent_comparison is True
    assert any("clean-room independence protocol" in b for b in readiness.blockers)
    assert len(readiness.warnings) == 1
    assert "prompt/context provenance" in readiness.warnings[0]


def test_codex_renderer_a_exposure_blocks_even_exploratory_comparison() -> None:
    declaration = _declaration()
    declaration["independence"]["llm_generated_mapping_code_used"] = True
    declaration["independence"][
        "renderer_a_outputs_inspected_before_initial_commit"
    ] = True

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )
    assert readiness.ready_for_differential_comparison is False
    assert readiness.ready_for_exploratory_agent_comparison is False


def test_codex_without_custodian_handoff_blocks_all_comparisons() -> None:
    declaration = _declaration()
    declaration["independence"]["llm_generated_mapping_code_used"] = True
    readiness = assess_renderer_b_declaration(declaration)
    assert not readiness.ready_for_differential_comparison
    assert not readiness.ready_for_exploratory_agent_comparison


def test_llm_mapping_provenance_must_be_explicit_even_for_direct_python_caller() -> None:
    declaration = _declaration()
    del declaration["independence"]["llm_generated_mapping_code_used"]
    readiness = assess_renderer_b_declaration(
        declaration, expected_clean_room_inputs=_expected_inputs()
    )
    assert not readiness.ready_for_differential_comparison
    assert not readiness.ready_for_exploratory_agent_comparison
    assert any("provenance is missing or invalid" in b for b in readiness.blockers)


def test_readiness_dict_always_distinguishes_exploratory_and_scientific() -> None:
    from fhirbridge.renderer_b_submission import renderer_b_readiness_to_dict

    declaration = _declaration()
    clean = assess_renderer_b_declaration(
        declaration, expected_clean_room_inputs=_expected_inputs()
    )
    assert renderer_b_readiness_to_dict(clean)["ready_for_differential_comparison"]
    assert not renderer_b_readiness_to_dict(clean)[
        "ready_for_exploratory_agent_comparison"
    ]
    declaration["independence"]["llm_generated_mapping_code_used"] = True
    agent = assess_renderer_b_declaration(
        declaration, expected_clean_room_inputs=_expected_inputs()
    )
    assert not renderer_b_readiness_to_dict(agent)[
        "ready_for_differential_comparison"
    ]
    assert renderer_b_readiness_to_dict(agent)[
        "ready_for_exploratory_agent_comparison"
    ]


def test_placeholders_block_comparison() -> None:
    declaration = deepcopy(_declaration())
    declaration["contributor"]["identity"] = (
        "TO_BE_COMPLETED_BY_INDEPENDENT_IMPLEMENTER"
    )
    declaration["known_unsupported_cases"] = [
        "TO_BE_COMPLETED_BY_INDEPENDENT_IMPLEMENTER"
    ]

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=_expected_inputs(),
    )

    assert readiness.ready_for_differential_comparison is False
    assert len(readiness.blockers) >= 2


def test_missing_custodian_handoff_blocks_comparison() -> None:
    readiness = assess_renderer_b_declaration(_declaration())

    assert not readiness.ready_for_differential_comparison
    assert any("expected clean-room input record" in x for x in readiness.blockers)


def test_clean_room_input_hash_mismatch_blocks_comparison() -> None:
    declaration = _declaration()
    expected = _expected_inputs()
    expected["challenge_manifest_sha256"] = "f" * 64

    readiness = assess_renderer_b_declaration(
        declaration,
        expected_clean_room_inputs=expected,
    )

    assert not readiness.ready_for_differential_comparison
    assert any("challenge_manifest_sha256" in x for x in readiness.blockers)



def test_exploratory_codex_gate_rejects_incomplete_direct_python_declarations() -> None:
    # Direct API callers historically bypassed shape checks performed by the
    # standalone renderer declaration CLI. No field may be omitted to obtain
    # a false "exploratory ready" result for a nominally AI-authored B.
    for path in (
        ("renderer_id",),
        ("renderer_version",),
        ("contributor", "identity"),
        ("contributor", "role"),
        ("implementation", "language"),
        ("implementation", "source_commit"),
        ("implementation_period", "started_on"),
        ("implementation_period", "completed_on"),
        ("clean_room_inputs", "contract_sha256"),
    ):
        declaration = _declaration()
        declaration["independence"]["llm_generated_mapping_code_used"] = True
        obj = declaration
        for part in path[:-1]:
            obj = obj[part]
        del obj[path[-1]]
        readiness = assess_renderer_b_declaration(
            declaration, expected_clean_room_inputs=_expected_inputs()
        )
        assert not readiness.ready_for_exploratory_agent_comparison, path
        assert not readiness.ready_for_differential_comparison, path
        assert any("schema invalid" in b for b in readiness.blockers), path


def test_exploratory_codex_gate_rejects_missing_fields_on_both_sides_of_handoff() -> None:
    for missing in (
        "challenge_id",
        "starting_commit",
        "challenge_manifest_sha256",
        "contract_sha256",
        "repository_full_name",
    ):
        declaration = _declaration()
        declaration["independence"]["llm_generated_mapping_code_used"] = True
        expected = _expected_inputs()
        # Matching None == None must never be confused with verified custody.
        del expected[missing]
        del declaration["clean_room_inputs"][missing]
        readiness = assess_renderer_b_declaration(
            declaration, expected_clean_room_inputs=expected
        )
        assert not readiness.ready_for_exploratory_agent_comparison, missing
        assert any("schema invalid" in b for b in readiness.blockers), missing


def test_no_raw_declaration_may_be_granted_exploratory_readiness() -> None:
    readiness = assess_renderer_b_declaration(
        None, expected_clean_room_inputs=_expected_inputs()
    )
    assert not readiness.ready_for_exploratory_agent_comparison
    assert not readiness.ready_for_differential_comparison
