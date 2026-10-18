from pathlib import Path

import pytest

from fhirbridge.artifact_bundle import (
    hash_artifact_bundle,
    hash_components_from_manifest,
)


def test_bundle_hash_is_path_order_invariant(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")

    first = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["a.txt", "b.txt"],
    )
    second = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["b.txt", "a.txt"],
    )

    assert first.sha256 == second.sha256
    assert first.files == second.files
    assert first.file_count == 2


def test_bundle_hash_changes_when_path_identity_changes(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")

    first = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["a.txt"],
    )
    second = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["b.txt"],
    )

    assert first.sha256 != second.sha256


def test_bundle_hash_changes_when_file_bytes_change(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("alpha", encoding="utf-8")
    first = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["a.txt"],
    )
    path.write_text("changed", encoding="utf-8")
    second = hash_artifact_bundle(
        repository_root=tmp_path,
        component_id="C",
        relative_paths=["a.txt"],
    )

    assert first.sha256 != second.sha256


@pytest.mark.parametrize(
    "paths",
    [
        ["a.txt", "a.txt"],
        ["../a.txt"],
        ["/absolute.txt"],
    ],
)
def test_bundle_hash_rejects_unsafe_or_duplicate_paths(
    tmp_path: Path,
    paths: list[str],
) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")

    with pytest.raises((ValueError, FileNotFoundError)):
        hash_artifact_bundle(
            repository_root=tmp_path,
            component_id="C",
            relative_paths=paths,
        )


def test_bundle_hash_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing"):
        hash_artifact_bundle(
            repository_root=tmp_path,
            component_id="C",
            relative_paths=["missing.txt"],
        )


def test_bundle_hash_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("alpha", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable in test environment")

    with pytest.raises(ValueError, match="symlink"):
        hash_artifact_bundle(
            repository_root=tmp_path,
            component_id="C",
            relative_paths=["link.txt"],
        )


def test_manifest_hashing_requires_supported_method(tmp_path: Path) -> None:
    document = {
        "instrument_component_manifest": {
            "hash_method": "unsupported",
        },
        "components": {
            "one": {
                "artifact_id": "one",
                "paths": ["a.txt"],
            }
        },
    }
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        hash_components_from_manifest(
            document,
            repository_root=tmp_path,
        )
