import pytest

import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"


def test_v2_renderer_refuses_to_silently_drop_v03_order_context() -> None:
    graph = fhirbridge.canonical.generate_lab_scenario(
        "LAB-001",
        9921,
        include_order_context=True,
    )
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)

    with pytest.raises(ValueError, match="order-context rendering is fail-closed"):
        fhirbridge.renderers.Hl7V251OruRendererA().render(
            graph,
            contract=contract,
        )


def test_v2_renderer_development_slice_still_renders_legacy_no_order_case() -> None:
    graph = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9922)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)

    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )

    assert rendered.artifact.startswith("MSH|")
    assert "\rOBR|" in rendered.artifact
