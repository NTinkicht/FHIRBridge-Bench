"""Render deterministic US Core order-context development fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
_PRIMARY_TEMPLATES = tuple(f"LAB-{index:03d}" for index in range(1, 12))


def main() -> int:
    output_dir = Path("qualification/fhir/order-context")
    output_dir.mkdir(parents=True, exist_ok=True)

    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    cases: list[dict[str, object]] = []
    for index, template_id in enumerate(_PRIMARY_TEMPLATES, start=1):
        seed = 9490 + index
        graph = fhirbridge.canonical.generate_lab_scenario(
            template_id,
            seed,
            include_order_context=True,
        )
        if graph["scenario_metadata"]["primary_endpoint_eligible"] is not True:
            continue
        rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
            graph,
            contract=contract,
        )
        output = output_dir / f"{template_id}-{seed}-order-context.json"
        output.write_text(
            json.dumps(rendered.artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        cases.append(
            {
                "template_id": template_id,
                "seed": seed,
                "graph_id": graph["graph_id"],
                "output": str(output),
            }
        )

    manifest = {
        "contract_version": contract["contract"]["version"],
        "renderer_id": fhirbridge.renderers.FhirR4LabRendererA().renderer_id,
        "renderer_version": fhirbridge.renderers.FhirR4LabRendererA().renderer_version,
        "case_count": len(cases),
        "cases": cases,
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
