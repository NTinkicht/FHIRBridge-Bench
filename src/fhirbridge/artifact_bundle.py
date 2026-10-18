"""Deterministic hashing of explicitly enumerated frozen artifact bundles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactBundleDigest:
    component_id: str
    sha256: str
    file_count: int
    files: tuple[dict[str, Any], ...]


def _validate_relative_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("artifact path must be a non-empty string")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError(f"absolute artifact path is prohibited: {raw}")
    if ".." in path.parts:
        raise ValueError(f"parent traversal is prohibited: {raw}")
    normalized = Path(*[part for part in path.parts if part not in {"", "."}])
    if not normalized.parts:
        raise ValueError("artifact path must not resolve to repository root")
    return normalized


def hash_artifact_bundle(
    *,
    repository_root: Path,
    component_id: str,
    relative_paths: list[str] | tuple[str, ...],
) -> ArtifactBundleDigest:
    """Hash an explicit path-bound file bundle.

    The component digest binds both relative path identity and exact file bytes.
    Local untracked files outside the enumeration cannot affect the result.
    """

    if not isinstance(component_id, str) or not component_id:
        raise ValueError("component_id must be a non-empty string")
    if not relative_paths:
        raise ValueError("relative_paths must not be empty")

    normalized: list[Path] = [
        _validate_relative_path(raw) for raw in relative_paths
    ]
    normalized_strings = [path.as_posix() for path in normalized]
    if len(normalized_strings) != len(set(normalized_strings)):
        raise ValueError(
            f"component {component_id} contains duplicate artifact paths"
        )

    file_rows: list[dict[str, Any]] = []
    for relative in sorted(normalized, key=lambda item: item.as_posix()):
        absolute = repository_root / relative
        if not absolute.exists():
            raise FileNotFoundError(
                f"component {component_id} artifact is missing: {relative.as_posix()}"
            )
        if absolute.is_symlink():
            raise ValueError(
                f"component {component_id} symlink is prohibited: "
                f"{relative.as_posix()}"
            )
        if not absolute.is_file():
            raise ValueError(
                f"component {component_id} artifact is not a file: "
                f"{relative.as_posix()}"
            )
        data = absolute.read_bytes()
        file_rows.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )

    canonical = "".join(
        f"{row['path']}\0{row['sha256']}\0{row['size_bytes']}\n"
        for row in file_rows
    ).encode("utf-8")
    digest = sha256(canonical).hexdigest()
    return ArtifactBundleDigest(
        component_id=component_id,
        sha256=digest,
        file_count=len(file_rows),
        files=tuple(file_rows),
    )


def hash_components_from_manifest(
    document: dict[str, Any],
    *,
    repository_root: Path,
) -> dict[str, ArtifactBundleDigest]:
    header = document.get("instrument_component_manifest")
    if not isinstance(header, dict):
        raise ValueError("instrument_component_manifest metadata is missing")
    if header.get("hash_method") != "path_bound_sha256_manifest_v1":
        raise ValueError("unsupported instrument component hash method")

    components = document.get("components")
    if not isinstance(components, dict) or not components:
        raise ValueError("instrument component definitions are missing")

    result: dict[str, ArtifactBundleDigest] = {}
    for component_name, component in components.items():
        if not isinstance(component, dict):
            raise ValueError(f"component {component_name} must be a mapping")
        artifact_id = component.get("artifact_id")
        paths = component.get("paths")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(f"component {component_name} lacks artifact_id")
        if not isinstance(paths, list) or not all(
            isinstance(item, str) for item in paths
        ):
            raise ValueError(f"component {component_name} paths must be strings")
        result[str(component_name)] = hash_artifact_bundle(
            repository_root=repository_root,
            component_id=artifact_id,
            relative_paths=paths,
        )
    return result
