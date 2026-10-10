"""Render a deterministic US Core order-context development fixture."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"


def main() -> int:
    output_dir = Path("qualification/fhir/order-context")
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = fhirbridge.canonical.generate_lab_scenario(
        "LAB-001",
        9491,
        include_order_context=True,
    )
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
        graph,
        contract=contract,
    )
    output = output_dir / "LAB-001-9491-order-context.json"
    output.write_text(
        json.dumps(rendered.artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "graph_id": graph["graph_id"],
        "contract_version": contract["contract"]["version"],
        "renderer_id": rendered.manifest.renderer_id,
        "renderer_version": rendered.manifest.renderer_version,
        "output": str(output),
        "scientific_role": "prefreeze_order_context_development_qualification",
        "confirmatory_evidence": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
