"""Hash provider-independent model-strategy artifacts for audit evidence."""

from __future__ import annotations

import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path

_OUTPUT = Path("models/generated/provider_independent_artifact_manifest.json")
_ARTIFACTS = (
    Path("models/execution_policy.yaml"),
    Path("models/prompts/direct_structured_v0.1.txt"),
    Path("models/prompts/mapping_aware_v0.1.txt"),
    Path("src/fhirbridge/model_strategies.py"),
    Path("src/fhirbridge/syntax_repair.py"),
    Path("src/fhirbridge/mapping_context.py"),
    Path("models/build_frozen_mapping_context.py"),
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _repository_commit() -> str:
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_manifest() -> dict[str, object]:
    missing = [str(path) for path in _ARTIFACTS if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing strategy artifacts: " + ", ".join(missing))

    return {
        "manifest_id": "FHIRBRIDGE-PROVIDER-INDEPENDENT-ARTIFACTS-001",
        "status": "prefreeze_provider_independent",
        "repository_commit": _repository_commit(),
        "artifacts": [
            {
                "path": str(path),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in _ARTIFACTS
        ],
        "scientific_scope": [
            "prompt_templates",
            "execution_policy",
            "strategy_assembly",
            "syntax_repair",
            "mapping_context_generation_code",
        ],
        "not_included": [
            "final_model_provider_snapshot",
            "final_frozen_mapping_context",
            "deterministic_baseline_order_projection",
        ],
    }


def main() -> int:
    manifest = build_manifest()
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
