"""Derive terminology coverage requirements from frozen benchmark generators."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from .canonical import generate_lab_scenario

_LAB_TEMPLATES = tuple(f"LAB-{index:03d}" for index in range(1, 13))


def collect_loinc_codes_from_graph(graph: dict[str, Any]) -> set[str]:
    """Collect LOINC codes that appear as canonical fact concepts."""

    codes: set[str] = set()
    for fact in graph.get("facts", []):
        if not isinstance(fact, dict):
            continue
        concept = fact.get("concept")
        if not isinstance(concept, dict):
            continue
        if concept.get("system") != "http://loinc.org":
            continue
        code = concept.get("code")
        if isinstance(code, str) and code:
            codes.add(code)
    return codes


def collect_lab_benchmark_loinc_codes(
    templates: Iterable[str] = _LAB_TEMPLATES,
) -> set[str]:
    """Collect every LOINC code reachable in the first laboratory benchmark slice.

    Seeds are deliberately fixed because terminology choice is template-driven,
    not random. The panel scenario guarantees coverage of all numeric analytes.
    """

    codes: set[str] = set()
    for index, template_id in enumerate(templates, start=1):
        graph = generate_lab_scenario(template_id, 9700 + index)
        codes.update(collect_loinc_codes_from_graph(graph))
    return codes


def required_loinc_codes_from_snapshot_requirements(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    required = document.get("required_codes") if isinstance(document, dict) else None
    if not isinstance(required, list):
        raise ValueError("LOINC requirements must define required_codes")

    codes: set[str] = set()
    for index, item in enumerate(required):
        if not isinstance(item, dict):
            raise ValueError(f"required_codes[{index}] must be a mapping")
        code = item.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError(f"required_codes[{index}].code must be non-empty")
        if code in codes:
            raise ValueError(f"duplicate required LOINC code: {code}")
        codes.add(code)
    return codes


def assert_loinc_snapshot_covers_benchmark(requirements_path: Path) -> None:
    """Fail if any benchmark LOINC code is absent from snapshot qualification."""

    benchmark_codes = collect_lab_benchmark_loinc_codes()
    required_codes = required_loinc_codes_from_snapshot_requirements(requirements_path)
    missing = sorted(benchmark_codes - required_codes)
    if missing:
        raise ValueError(
            "LOINC snapshot requirements do not cover benchmark codes: "
            + ", ".join(missing)
        )
