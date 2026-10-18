"""Build the frozen mapping context for confirmatory mapping-aware arms."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import yaml

from fhirbridge.mapping_context import (
    build_frozen_mapping_context,
    mapping_context_json,
)

_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_STATUS = Path("benchmark/status_mapping_candidates.yaml")
_SPECIMEN = Path("benchmark/specimen_binding_candidates.yaml")
_PROFILE = Path("benchmark/hl7v2_lri_profile_pin.yaml")
_OUTPUT = Path("models/generated/frozen_mapping_context.json")
_MANIFEST = Path("models/generated/frozen_mapping_context_manifest.json")


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def main() -> int:
    context = build_frozen_mapping_context(
        _load(_CONTRACT),
        _load(_STATUS),
        _load(_SPECIMEN),
        _load(_PROFILE),
    )
    text = mapping_context_json(context) + "\n"
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(text, encoding="utf-8")
    digest = sha256(text.encode("utf-8")).hexdigest()
    manifest = {
        "context_id": context["context_id"],
        "output": str(_OUTPUT),
        "sha256": digest,
        "contract_version": context["contract"]["version"],
        "target_profile": context["target"]["profile"],
        "included_rule_count": len(context["rules"]),
        "excluded_indeterminate_rule_ids": context[
            "excluded_indeterminate_rule_ids"
        ],
    }
    _MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
