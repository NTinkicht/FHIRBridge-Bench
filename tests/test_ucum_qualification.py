from math import isclose

import yaml

from fhirbridge.ucum_qualification import (
    load_unit_qualification_cases,
    qualify_unit_provider,
)
from fhirbridge.verifier.equivalence import EquivalenceResult, ExactUnitEquivalence

_MATRIX_PATH = "benchmark/ucum_lab_conversion_matrix.yaml"


class _DimensionScaleProvider:
    _UNITS = {
        "g/dL": ("mass_concentration", 10.0),
        "g/L": ("mass_concentration", 1.0),
        "mg/dL": ("mass_concentration", 0.01),
        "mg/L": ("mass_concentration", 0.001),
        "ug/mL": ("mass_concentration", 0.001),
        "mmol/L": ("amount_concentration", 0.001),
        "mol/L": ("amount_concentration", 1.0),
        "mL": ("volume", 0.001),
        "L": ("volume", 1.0),
    }

    def equivalent(
        self,
        source_value: float,
        source_unit: str,
        target_value: float,
        target_unit: str,
    ) -> EquivalenceResult:
        source = self._UNITS.get(source_unit)
        target = self._UNITS.get(target_unit)
        if source is None or target is None or source[0] != target[0]:
            return EquivalenceResult(
                equivalent=False,
                rationale_code="INCOMPATIBLE_DIMENSIONS",
                details={},
            )
        source_base = source_value * source[1]
        target_base = target_value * target[1]
        equivalent = isclose(source_base, target_base, rel_tol=1e-12, abs_tol=1e-12)
        return EquivalenceResult(
            equivalent=equivalent,
            rationale_code="SAME_BASE_QUANTITY" if equivalent else "QUANTITY_MISMATCH",
            details={"source_base": source_base, "target_base": target_base},
        )


def _matrix() -> dict:
    with open(_MATRIX_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_lab_ucum_matrix_is_well_formed_and_unique() -> None:
    matrix_id, version, cases = load_unit_qualification_cases(_matrix())

    assert matrix_id == "FHIRBRIDGE-UCUM-LAB-001"
    assert version == "0.1.0"
    assert len(cases) == 10
    assert len({case.case_id for case in cases}) == len(cases)
    assert any(case.expected_equivalent for case in cases)
    assert any(not case.expected_equivalent for case in cases)


def test_dimension_scale_provider_passes_project_matrix() -> None:
    report = qualify_unit_provider(_DimensionScaleProvider(), _matrix())

    assert report.total_cases == 10
    assert report.passed_cases == 10
    assert report.failed_cases == 0
    assert report.all_passed
    assert all(outcome.exception is None for outcome in report.outcomes)


def test_exact_unit_baseline_is_not_misrepresented_as_conversion_provider() -> None:
    report = qualify_unit_provider(ExactUnitEquivalence(), _matrix())

    assert not report.all_passed
    assert report.failed_cases > 0
    failed_ids = {outcome.case_id for outcome in report.outcomes if not outcome.passed}
    assert {"UQ-001", "UQ-002", "UQ-003", "UQ-004", "UQ-005", "UQ-006"} <= failed_ids


def test_provider_exception_is_recorded_as_failed_qualification() -> None:
    class _ExplodingProvider:
        def equivalent(self, *args, **kwargs):
            raise RuntimeError("provider unavailable")

    report = qualify_unit_provider(_ExplodingProvider(), _matrix())

    assert not report.all_passed
    assert report.failed_cases == report.total_cases
    assert all(outcome.exception for outcome in report.outcomes)
