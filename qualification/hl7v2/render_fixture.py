"""Render one deterministic development ORU^R01 for NIST harness smoke tests."""

from __future__ import annotations

from pathlib import Path

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def main() -> None:
    graph = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9501)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )

    output = Path("qualification/hl7v2/dev-message.er7")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered.artifact, encoding="utf-8")


if __name__ == "__main__":
    main()
