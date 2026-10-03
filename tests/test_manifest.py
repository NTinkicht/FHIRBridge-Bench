from fhirbridge.canonical import PartitionPlan, build_lab_manifest


def test_manifest_is_deterministic_for_same_seed() -> None:
    first = build_lab_manifest(base_seed=20261003)
    second = build_lab_manifest(base_seed=20261003)
    assert first == second


def test_manifest_changes_when_base_seed_changes() -> None:
    first = build_lab_manifest(base_seed=20261003)
    second = build_lab_manifest(base_seed=20261004)
    assert first["manifest_sha256"] != second["manifest_sha256"]
    assert {entry["seed"] for entry in first["entries"]} != {
        entry["seed"] for entry in second["entries"]
    }


def test_manifest_case_ids_and_seeds_are_unique() -> None:
    manifest = build_lab_manifest(base_seed=99)
    case_ids = [entry["case_id"] for entry in manifest["entries"]]
    seeds = [entry["seed"] for entry in manifest["entries"]]

    assert len(case_ids) == len(set(case_ids))
    assert len(seeds) == len(set(seeds))


def test_confirmatory_partition_contains_held_out_variants() -> None:
    plan = PartitionPlan(
        development_per_template=1,
        pilot_per_template=1,
        confirmatory_per_template=10,
        held_out_variant_fraction=0.2,
    )
    manifest = build_lab_manifest(base_seed=123, plan=plan)
    confirmatory = [
        entry for entry in manifest["entries"] if entry["partition"] == "confirmatory"
    ]

    variants = {entry["implementation_variant_id"] for entry in confirmatory}
    assert "canonical_profile" in variants
    assert "held_out_variant_a" in variants
    assert "held_out_variant_b" in variants

    for template_id in {entry["template_id"] for entry in confirmatory}:
        template_entries = [
            entry for entry in confirmatory if entry["template_id"] == template_id
        ]
        held_out = [
            entry
            for entry in template_entries
            if entry["implementation_variant_id"].startswith("held_out_variant_")
        ]
        assert len(held_out) == 2


def test_lab_012_is_development_only_and_not_primary_eligible() -> None:
    manifest = build_lab_manifest(base_seed=321)
    ambiguity = [entry for entry in manifest["entries"] if entry["template_id"] == "LAB-012"]

    assert len(ambiguity) == 1
    assert ambiguity[0]["partition"] == "development"
    assert ambiguity[0]["primary_endpoint_eligible"] is False
    assert ambiguity[0]["purpose"] == "ambiguity_and_contract_sensitivity"


def test_default_manifest_size_is_explicit() -> None:
    manifest = build_lab_manifest(base_seed=11)
    eligible = [entry for entry in manifest["entries"] if entry["primary_endpoint_eligible"]]

    expected = 11 * (3 + 2 + 10)
    assert len(eligible) == expected
    assert len(manifest["entries"]) == expected + 1
