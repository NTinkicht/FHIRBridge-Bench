"""Build the frozen development input package for clean-room Renderer B."""

from __future__ import annotations

import json
from pathlib import Path

from fhirbridge.renderer_b_challenge import write_renderer_b_challenge


def main() -> int:
    output = Path("renderer_validation/renderer_b_challenge")
    manifest = write_renderer_b_challenge(output)
    print(
        json.dumps(
            {
                "challenge_id": manifest["challenge_id"],
                "version": manifest["version"],
                "case_count": len(manifest["cases"]),
                "manifest_sha256": manifest["manifest_sha256"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
