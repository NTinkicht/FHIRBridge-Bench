import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path("qualification/hl7v2/hash_validator_runtime.py")
_SPEC = importlib.util.spec_from_file_location(
    "hash_validator_runtime",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_runtime_classpath_manifest_is_order_independent_by_label(
    tmp_path: Path,
) -> None:
    first = tmp_path / "repository/gov/example/a/1.0/a-1.0.jar"
    second = tmp_path / "repository/gov/example/b/1.0/b-1.0.jar"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    cp1 = tmp_path / "cp1.txt"
    cp2 = tmp_path / "cp2.txt"
    cp1.write_text(f"{first}:{second}\n", encoding="utf-8")
    cp2.write_text(f"{second}:{first}\n", encoding="utf-8")

    one = _MODULE.build_runtime_classpath_manifest(cp1)
    two = _MODULE.build_runtime_classpath_manifest(cp2)

    assert one == two
    assert one["artifact_count"] == 2
    assert len(one["runtime_classpath_sha256"]) == 64


def test_runtime_classpath_manifest_changes_when_jar_bytes_change(
    tmp_path: Path,
) -> None:
    jar = tmp_path / "repository/gov/example/a/1.0/a-1.0.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"a")
    cp = tmp_path / "classpath.txt"
    cp.write_text(str(jar), encoding="utf-8")

    first = _MODULE.build_runtime_classpath_manifest(cp)
    jar.write_bytes(b"changed")
    second = _MODULE.build_runtime_classpath_manifest(cp)

    assert first["runtime_classpath_sha256"] != second[
        "runtime_classpath_sha256"
    ]


def test_runtime_classpath_manifest_rejects_missing_artifact(
    tmp_path: Path,
) -> None:
    cp = tmp_path / "classpath.txt"
    cp.write_text(str(tmp_path / "missing.jar"), encoding="utf-8")

    try:
        _MODULE.build_runtime_classpath_manifest(cp)
    except FileNotFoundError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing classpath artifact must fail")


def test_runtime_classpath_manifest_serializes_expected_evidence(
    tmp_path: Path,
) -> None:
    jar = tmp_path / "lib/gov/example/a/1.0/a-1.0.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"content")
    cp = tmp_path / "classpath.txt"
    cp.write_text(str(jar), encoding="utf-8")

    manifest = _MODULE.build_runtime_classpath_manifest(cp)
    encoded = json.dumps(manifest, sort_keys=True)

    assert "lib/gov/example/a/1.0/a-1.0.jar" in encoded
    assert manifest["hash_method"] == (
        "stable_label_sha256_size_manifest_v1"
    )
