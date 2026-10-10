"""Render deterministic FHIR qualification fixtures for external validation."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
_CASES = (
    ("LAB-001", 9401),
    ("LAB-004", 9402),
    ("LAB-006", 9403),
    ("LAB-011", 9404),
)


def main() -> None:
    output_dir = Path("qualification/fhir/out")
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)

    manifest: list[dict[str, object]] = []
    for template_id, seed in _CASES:
        graph = fhirbridge.canonical.generate_lab_scenario(template_id, seed)
        rendered = fhirbridge.renderers.FhirR4LabRendererA().render(
            graph,
            contract=contract,
        )
        output_path = output_dir / f"{template_id}-{seed}.json"
        output_path.write_text(
            json.dumps(rendered.artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest.append(
            {
                "template_id": template_id,
                "seed": seed,
                "graph_id": graph["graph_id"],
                "output": str(output_path),
                "renderer_id": rendered.manifest.renderer_id,
                "renderer_version": rendered.manifest.renderer_version,
                "contract_version": contract["contract"]["version"],
                "order_context": False,
                "scientific_role": "legacy_order_free_development_diagnostic",
            }
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
