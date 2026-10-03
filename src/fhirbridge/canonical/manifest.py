"""Deterministic benchmark-manifest generation.

The manifest fixes scenario template, seed, implementation variant, and partition
before confirmatory model inference. It contains no rendered FHIR or HL7 v2.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

_TEMPLATE_IDS = tuple(f"LAB-{index:03d}" for index in range(1, 13))
_PRIMARY_TEMPLATE_IDS = tuple(template for template in _TEMPLATE_IDS if template != "LAB-012")


@dataclass(frozen=True)
class PartitionPlan:
    development_per_template: int = 3
    pilot_per_template: int = 2
    confirmatory_per_template: int = 10
    held_out_variant_fraction: float = 0.2

    def __post_init__(self) -> None:
        counts = (
            self.development_per_template,
            self.pilot_per_template,
            self.confirmatory_per_template,
        )
        if any(count < 0 for count in counts):
            raise ValueError("partition counts must be non-negative")
        if not 0 <= self.held_out_variant_fraction <= 1:
            raise ValueError("held_out_variant_fraction must be in [0, 1]")


def _stable_seed(base_seed: int, template_id: str, partition: str, index: int) -> int:
    material = f"{base_seed}|{template_id}|{partition}|{index}".encode()
    digest = sha256(material).digest()
    return int.from_bytes(digest[:8], "big") % 2_000_000_000


def _variant_for(
    *,
    partition: str,
    index: int,
    count: int,
    held_out_fraction: float,
) -> str:
    if partition != "confirmatory" or count == 0:
        return "canonical_profile"

    held_out_count = round(count * held_out_fraction)
    if held_out_count <= 0:
        return "canonical_profile"

    threshold = count - held_out_count
    if index < threshold:
        return "canonical_profile"
    return "held_out_variant_a" if (index - threshold) % 2 == 0 else "held_out_variant_b"


def build_lab_manifest(
    *,
    base_seed: int,
    plan: PartitionPlan | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest for development, pilot, and confirmatory cases."""

    active_plan = plan or PartitionPlan()
    entries: list[dict[str, Any]] = []

    partitions = (
        ("development", active_plan.development_per_template),
        ("pilot", active_plan.pilot_per_template),
        ("confirmatory", active_plan.confirmatory_per_template),
    )

    for partition, count in partitions:
        for template_id in _PRIMARY_TEMPLATE_IDS:
            for index in range(count):
                seed = _stable_seed(base_seed, template_id, partition, index)
                variant = _variant_for(
                    partition=partition,
                    index=index,
                    count=count,
                    held_out_fraction=active_plan.held_out_variant_fraction,
                )
                entries.append(
                    {
                        "case_id": f"{partition}-{template_id}-{index:04d}",
                        "template_id": template_id,
                        "seed": seed,
                        "partition": partition,
                        "implementation_variant_id": variant,
                        "primary_endpoint_eligible": True,
                    }
                )

    ambiguity_seed = _stable_seed(base_seed, "LAB-012", "development", 0)
    entries.append(
        {
            "case_id": "development-LAB-012-0000",
            "template_id": "LAB-012",
            "seed": ambiguity_seed,
            "partition": "development",
            "implementation_variant_id": "canonical_profile",
            "primary_endpoint_eligible": False,
            "purpose": "ambiguity_and_contract_sensitivity",
        }
    )

    payload = {
        "manifest_version": "0.1.0",
        "base_seed": base_seed,
        "plan": {
            "development_per_template": active_plan.development_per_template,
            "pilot_per_template": active_plan.pilot_per_template,
            "confirmatory_per_template": active_plan.confirmatory_per_template,
            "held_out_variant_fraction": active_plan.held_out_variant_fraction,
        },
        "entries": entries,
    }
    canonical = repr(payload).encode("utf-8")
    payload["manifest_sha256"] = sha256(canonical).hexdigest()
    return payload
