from fhirbridge.verifier import LiftedFact, ground_graph, ground_source_fact


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


def _target_observation(
    *,
    lifted_id: str,
    time: str,
    value: float,
    subject_ref: str = "target-patient-1",
    report_ref: str = "target-report-1",
) -> LiftedFact:
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="observation",
        subject_ref=subject_ref,
        semantic_payload={
            "concept": {"system": "http://loinc.org", "code": "2345-7"},
            "value": value,
            "unit": {"system": "http://unitsofmeasure.org", "code": "mg/dL"},
            "temporal": {"effective_start": time},
            "identifiers": [],
        },
        target_paths=("OBX-3", "OBX-5", "OBX-14"),
        relationships=(("belongs_to_report", report_ref),),
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

    result = ground_source_fact(
        source,
        [early, matching],
        reference_map={
            "patient-1": "target-patient-1",
            "report-1": "target-report-1",
        },
    )

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

    result = ground_source_fact(
        source,
        [first, second],
        reference_map={
            "patient-1": "target-patient-1",
            "report-1": "target-report-1",
        },
    )

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
        subject_ref="target-patient-1",
        semantic_payload={},
        target_paths=("OBR",),
    )

    result = ground_source_fact(source, [target])

    assert result.status == "unmatched"
    assert result.rationale_code == "NO_GROUNDING_CANDIDATE"


def test_subject_mismatch_is_penalized_after_identity_is_resolved() -> None:
    source = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    target = _target_observation(
        lifted_id="lifted-wrong-patient",
        time="2026-09-20T08:15:00+04:00",
        value=92,
        subject_ref="target-patient-2",
    )

    result = ground_source_fact(
        source,
        [target],
        minimum_score=20,
        reference_map={
            "patient-1": "target-patient-1",
            "report-1": "target-report-1",
        },
    )

    assert result.status == "unmatched"


def test_raw_representation_ids_are_not_required_to_match() -> None:
    source = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    target = _target_observation(
        lifted_id="lifted-obs-abc",
        time="2026-09-20T08:15:00+04:00",
        value=92,
        subject_ref="Patient/abc",
        report_ref="DiagnosticReport/xyz",
    )

    result = ground_source_fact(
        source,
        [target],
        reference_map={
            "patient-1": "Patient/abc",
            "report-1": "DiagnosticReport/xyz",
        },
    )

    assert result.status == "grounded"
    assert result.target_fact_id == "lifted-obs-abc"
    assert "subject_identity" in result.evidence["matched_keys"]


def test_graph_grounding_propagates_patient_identity_to_dependent_facts() -> None:
    source_patient = {
        "fact_id": "patient-1",
        "fact_type": "patient_identity",
        "subject_ref": "patient-1",
        "identifiers": [{"system": "urn:mrn", "value": "123"}],
        "relations": [],
    }
    source_observation = _source_observation(
        fact_id="obs-1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
    )
    target_patient = LiftedFact(
        lifted_fact_id="Patient/abc",
        fact_type="patient_identity",
        subject_ref="Patient/abc",
        semantic_payload={
            "identifiers": [{"system": "urn:mrn", "value": "123"}],
        },
        target_paths=("Patient.identifier",),
    )
    target_observation = _target_observation(
        lifted_id="Observation/obs1",
        time="2026-09-20T08:15:00+04:00",
        value=92,
        subject_ref="Patient/abc",
        report_ref="target-report-1",
    )

    results = ground_graph(
        [source_observation, source_patient],
        [target_observation, target_patient],
    )

    assert results["patient-1"].status == "grounded"
    assert results["patient-1"].target_fact_id == "Patient/abc"
    assert results["obs-1"].status == "grounded"
    assert results["obs-1"].target_fact_id == "Observation/obs1"
