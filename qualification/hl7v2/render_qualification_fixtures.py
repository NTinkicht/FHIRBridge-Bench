"""Render one deterministic ORU^R01 plus structural negative controls."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation
from fhirbridge.hl7v2_negative_controls import build_structural_negative_controls

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def main() -> None:
    output_dir = Path("qualification/hl7v2/fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9501)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )

    baseline_path = output_dir / "baseline-LAB-001-9501.er7"
    baseline_path.write_text(rendered.artifact, encoding="utf-8")

    controls = build_structural_negative_controls(rendered.artifact)
    manifest = {
        "baseline": str(baseline_path),
        "renderer_id": rendered.manifest.renderer_id,
        "renderer_version": rendered.manifest.renderer_version,
        "controls": [],
    }
    for control in controls:
        path = output_dir / f"{control.control_id}.er7"
        path.write_text(control.artifact, encoding="utf-8")
        manifest["controls"].append(
            {
                "control_id": control.control_id,
                "description": control.description,
                "path": str(path),
                "expected_structural_error": control.expected_structural_error,
            }
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
