"""Blind Path B handoff must not re-introduce the obsolete XML dependency."""

import runpy
from pathlib import Path

_BUILDER = Path(
    "qualification/hl7v2/required_element_review/build_blind_packet.py"
)


def test_path_b_readme_pins_both_normative_publication_documents() -> None:
    module = runpy.run_path(str(_BUILDER))
    readme = module["_readme"]()
    assert module["_SOURCE_SHA256"] in readme
    assert module["_ERRATA_SHA256"] in readme
    assert "December 2024 errata-letter PDF SHA-256" in readme
    assert "full conformance" in readme
    assert "full_edition5_profile_conformance_claim" not in readme


def test_packet_allows_pdf_extraction_without_original_machine_bundle() -> None:
    readme = " ".join(runpy.run_path(str(_BUILDER))["_readme"]().split())
    assert "NOT a claim" in readme
    assert "not required to start Path B extraction" in readme
    assert "separately qualified sensitivity comparator" in readme
    assert "A matching or schema-valid extraction alone does not establish" in readme
    assert "reconciliation is mandatory" not in readme
    assert "project-authored requirement inventories" in readme or (
        "project implementation" in readme
    )


def test_blind_packet_handoff_does_not_include_renderer_or_project_inventory() -> None:
    module = runpy.run_path(str(_BUILDER))
    readme = module["_readme"]().lower()
    assert "hl7v251_oru_a.py" not in readme
    assert "benchmark/lri_required_element_inventory.yaml" not in readme
    assert "do not use another extractor's work" in readme
