import pytest
import yaml

from fhirbridge.lri_required_inventory import assess_required_element_inventory

_PATH = "benchmark/lri_required_element_inventory.yaml"


def _inventory() -> dict:
    with open(_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_current_required_element_inventory_is_explicitly_incomplete() -> None:
    readiness = assess_required_element_inventory(_inventory())

    assert readiness.ready is False
    assert "inventory.status is not complete" in readiness.blockers
    assert any("reader_b" in blocker for blocker in readiness.blockers)
    assert any("inventory domains remain unresolved" in blocker for blocker in readiness.blockers)
    assert any("machine-readable Edition 5 bundle" in blocker for blocker in readiness.blockers)


def test_inventory_cannot_claim_complete_with_unresolved_domains() -> None:
    document = _inventory()
    document["inventory"]["status"] = "complete"

    with pytest.raises(ValueError, match="cannot be marked complete"):
        assess_required_element_inventory(document)


def test_known_order_entries_are_page_anchored_without_freezing_orc1_value() -> None:
    document = _inventory()
    entries = {item["element"]: item for item in document["verified_entries"]}

    assert entries["ORC-1"]["usage"] == "R"
    assert entries["ORC-1"]["cardinality"] == "1..1"
    assert entries["ORC-1"]["classification"] == "UNRESOLVED"
    assert "value_semantics_unresolved" in entries["ORC-1"]["verification_status"]
    assert entries["ORC-3"]["classification"] == "SOURCE_FACT"
    assert entries["ORC-12"]["classification"] == "SOURCE_FACT"
    assert entries["OBR-16"]["edition5_pages"] == [190]


def test_structural_equalities_are_not_semantic_equivalence_rules() -> None:
    document = _inventory()

    assert {
        item["constraint"] for item in document["verified_co_constraints"]
    } == {
        "ORC-2_equals_OBR-2_when_present",
        "ORC-3_equals_OBR-3",
        "ORC-12_equals_OBR-16",
    }
    assert {
        item["role"] for item in document["verified_co_constraints"]
    } == {"structural_conformance"}
