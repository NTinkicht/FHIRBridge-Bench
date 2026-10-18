import importlib.util
import re
from pathlib import Path

_MODULE_PATH = Path("renderer_validation/build_renderer_b_expected_inputs.py")
_SPEC = importlib.util.spec_from_file_location("build_renderer_b_expected_inputs", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_record = _MODULE.build_record


def test_renderer_b_handoff_record_is_deterministic_for_fixed_inputs() -> None:
    kwargs = {
        "starting_commit": "1" * 40,
        "created_at": "2026-10-10T14:25:06Z",
    }

    first = build_record(**kwargs)
    second = build_record(**kwargs)

    assert first == second
    inputs = first["clean_room_inputs"]
    assert inputs["repository_full_name"] == "NTinkicht/FHIRBridge-Bench"
    assert inputs["branch"] == "renderer-b-cleanroom"
    assert inputs["starting_commit"] == "1" * 40
    assert inputs["challenge_id"] == "FHIRBRIDGE-RENDERER-B-DEV-001"
    assert inputs["challenge_version"] == "0.3.0"
    assert re.fullmatch(r"[0-9a-f]{64}", inputs["challenge_manifest_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", inputs["contract_sha256"])


def test_renderer_b_handoff_rejects_short_or_zero_starting_commit() -> None:
    for value in ("abcdef1", "0" * 40):
        try:
            build_record(
                starting_commit=value,
                created_at="2026-10-10T14:25:06Z",
            )
        except ValueError as exc:
            assert "starting_commit" in str(exc)
        else:
            raise AssertionError("invalid starting commit was accepted")
