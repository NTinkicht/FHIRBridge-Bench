"""Hash the exact Java runtime classpath used by the HL7 v2 validator."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _stable_label(path: Path) -> str:
    parts = path.as_posix().split("/")
    for marker in ("repository", "lib"):
        if marker in parts:
            index = len(parts) - 1 - parts[::-1].index(marker)
            suffix = "/".join(parts[index + 1 :])
            if suffix:
                return f"{marker}/{suffix}"
    return path.name


def build_runtime_classpath_manifest(
    classpath_file: Path,
) -> dict[str, object]:
    raw = classpath_file.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("validator runtime classpath is empty")

    entries: list[dict[str, object]] = []
    seen_labels: set[str] = set()
    for token in raw.split(":"):
        if not token:
            continue
        path = Path(token)
        if not path.is_file():
            raise FileNotFoundError(f"classpath artifact is missing: {path}")
        label = _stable_label(path)
        if label in seen_labels:
            raise ValueError(f"duplicate stable classpath label: {label}")
        seen_labels.add(label)
        entries.append(
            {
                "label": label,
                "filename": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )

    if not entries:
        raise ValueError("validator runtime classpath has no file entries")
    entries.sort(key=lambda item: str(item["label"]))
    canonical = "".join(
        f"{item['label']}\0{item['sha256']}\0{item['size_bytes']}\n"
        for item in entries
    ).encode("utf-8")
    return {
        "schema_version": "0.1.0",
        "hash_method": "stable_label_sha256_size_manifest_v1",
        "artifact_count": len(entries),
        "artifacts": entries,
        "runtime_classpath_sha256": sha256(canonical).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("classpath_file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = build_runtime_classpath_manifest(args.classpath_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
