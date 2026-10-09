# Renderer B Challenge Handoff

This file pins the exact canonical-only development challenge package prepared for the independent Renderer B implementation.

## Pinned challenge artifact

- Protocol source commit: `793a187c33c3df0814edc2881411aa8bd86075e0`
- Protocol Validation run: `#682`
- Workflow run ID: `37995759843`
- Artifact name: `renderer-b-development-challenge-37995759843`
- Artifact ID: `11646189211`
- Artifact URL: https://github.com/NTinkicht/FHIRBridge-Bench/actions/runs/37995759843/artifacts/11646189211
- Downloaded ZIP SHA-256: `70ac8376ac2cba193859a953bc7b190e4738927c4f6763f3cb6147b47b3dd215`
- Challenge manifest SHA-256: `2e5bed0d72744cb32d2b175af5bb5a37fa1f56e26e71405d4accbfd55b1919b0`

Access to the artifact follows the repository's GitHub permissions.

## Scientific contents

The package contains exactly one deterministic canonical development graph for each `LAB-001` through `LAB-012`, under `inputs/RB-001.json` through `inputs/RB-012.json`, plus `manifest.json`.

The manifest explicitly records:

- `contains_renderer_a_output: false`
- `contains_target_gold_serialization: false`
- `contains_verifier_decisions: false`
- `contains_fault_labels: false`
- partition: `development`
- contract version: `0.2.0`

`LAB-001` through `LAB-011` are marked primary-endpoint eligible for this development challenge. `LAB-012` is deliberately marked `INDETERMINATE` and non-primary; it must not be forced into a serialization simply to maximize coverage.

## Clean-room use

1. Download the pinned artifact from the link above while staying on this isolated branch.
2. Verify the ZIP SHA-256 before extracting it.
3. Verify `manifest.json` reports manifest SHA-256 `2e5bed0d72744cb32d2b175af5bb5a37fa1f56e26e71405d4accbfd55b1919b0`.
4. Verify every extracted graph against the per-case `graph_sha256` recorded in the manifest.
5. Implement Renderer B and its independent tests without inspecting any prohibited branch/source listed in `CLEANROOM_README.md`.
6. Commit the initial Renderer B implementation and tests before any Renderer A output is exposed.
7. Complete the machine-readable Renderer B implementation declaration before differential comparison.

Do not use the historical NIST comparator, Renderer A output, lifter output, verifier decisions, or seeded-fault labels as target gold while implementing Renderer B.

This package is an input challenge, not a correctness oracle.
