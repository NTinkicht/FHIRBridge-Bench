"""JSON schema consulted by readiness must be wheel-safe and source-identical."""

import json
import tomllib
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from fhirbridge.lri_required_element_review import assess_required_element_extraction

_SOURCE = Path(
    "qualification/hl7v2/required_element_review/schema/required_element_extraction.schema.json"
)


def test_runtime_schema_is_identical_to_authoritative_blind_response_schema() -> None:
    expected = json.loads(_SOURCE.read_text(encoding="utf-8"))
    packaged = json.loads(
        files("fhirbridge")
        .joinpath("required_element_extraction.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(packaged)
    assert packaged == expected


def test_wheel_explicitly_includes_response_schema_resource() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    included = project["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert included["src/fhirbridge/required_element_extraction.schema.json"] == (
        "fhirbridge/required_element_extraction.schema.json"
    )


def test_readiness_rejects_non_mapping_input_as_unqualified() -> None:
    readiness = assess_required_element_extraction([])  # type: ignore[arg-type]
    assert not readiness.ready
    assert "not an object" in readiness.blockers[0]
