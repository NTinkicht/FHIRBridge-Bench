from fhirbridge.verifier import LiftedFact, ground_source_fact


def _source_observation(*, fact_id: str, time: str, value: float) -> dict:
    return {
        "fact_id": fact_id,
        "fact_type": "observation",
        "subject_ref": "patient-1",
        "concept": {"system": "http://loinc.org", "code": "2345-7"},
        "value": value,
        "unit": {"system": "http://unitsofmeasure.org", "code": "mg/dL"},
        "temporal": {"effective_start": time},
        "identifiers": [],
        "relations": [
            {"relation_type": "belongs_to_report", "target_fact_id": "report-1"}
        ],
    }


def _target_observation(*, lifted_id: str, time: str, value: float) -> LiftedFact:
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="observation",
        subject_ref="patient-1",
        semantic_payload={
            "concept": {"system": "http://loinc.org", "code": "2345-7"},
            "value": value,
            "unit": {"system": "http://unitsofmeasure.org", "code": "mg/dL"},
            "temporal": {"effective_start": time},
            "identifiers": [],
        },
        target_paths=("OBX-3", "OBX-5", "OBX-14"),
        relationships=(("belongs_to_report", "report-1"),),
    )


def test_grounding_uses_temporal_context_for_repeated_same_code() -> None:
    source = _source_observation(
        fact_id="obs-2",
        time="2026-09-20T09:15:00+04:00",
        value=98,
    )
    early = _target_observation(
        lifted_id="lifted-early",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    matching = _target_observation(
        lifted_id="lifted-matching",
        time="2026-09-20T09:15:00+04:00",
        value=97,
    )

    result = ground_source_fact(source, [early, matching])

    assert result.status == "grounded"
    assert result.target_fact_id == "lifted-matching"
    assert result.rationale_code == "UNIQUE_BEST_GROUNDING"


def test_grounding_reports_tie_as_ambiguous_instead_of_guessing() -> None:
    source = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    first = _target_observation(
        lifted_id="lifted-a",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    second = _target_observation(
        lifted_id="lifted-b",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )

    result = ground_source_fact(source, [first, second])

    assert result.status == "ambiguous"
    assert result.target_fact_id is None
    assert {candidate.target_fact_id for candidate in result.candidates} == {
        "lifted-a",
        "lifted-b",
    }


def test_grounding_does_not_match_different_fact_type() -> None:
    source = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    target = LiftedFact(
        lifted_fact_id="lifted-report",
        fact_type="diagnostic_report",
        subject_ref="patient-1",
        semantic_payload={},
        target_paths=("OBR",),
    )

    result = ground_source_fact(source, [target])

    assert result.status == "unmatched"
    assert result.rationale_code == "NO_GROUNDING_CANDIDATE"


def test_grounding_penalizes_wrong_patient_attribution() -> None:
    source = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    target = LiftedFact(
        lifted_fact_id="lifted-wrong-patient",
        fact_type="observation",
        subject_ref="patient-2",
        semantic_payload={
            "concept": {"system": "http://loinc.org", "code": "2345-7"},
            "temporal": {"effective_start": "2026-09-20T08:15:00+04:00"},
            "identifiers": [],
        },
        target_paths=("OBX-3",),
    )

    result = ground_source_fact(source, [target], minimum_score=20)

    assert result.status == "unmatched"
