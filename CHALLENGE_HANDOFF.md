# Renderer B — Current Isolated Codex Challenge Handoff (v0.3.0)

This clean-room branch contains **only permitted development inputs**. Its previous
v0.2.0 handoff reference (workflow run 37995759843, manifest 2e5bed...) is
**superseded and must not be used**, because it predates sanitized answer-hint
removal. The old artifact and starting commit are retained only for historical
provenance; they are not current Codex implementation inputs.

## Current immutable source identities

- Challenge ID: `FHIRBRIDGE-RENDERER-B-DEV-001`
- Challenge version: **0.3.0** — twelve synthetic development cases RB-001…RB-012
- Sanitized challenge manifest SHA-256: `668a0e90b9ba9a7679084e442a7d22fb5ffa518fc94cf61b6bd348e2fb59d966`
- Draft contract: `contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml`
- Draft contract byte SHA-256: `7058513c8541e175d2368a6698f285a594f13cde58cd0f4b6455c7cac95b4ac5`
- Exact `starting_commit`: **do not hardcode here**. It is recorded in the
  matching **custodian-generated** `renderer-b-expected-inputs.yaml` issued
  after this branch's final merge. The `created_at` timestamp also comes from
  the custodian record, not from this static document.

## Actual handoff artifacts

Obtain the **same single successful, exact-head** Protocol validation workflow
run in `protocol-v1` and download these two Actions artifacts:

1. `renderer-b-development-challenge-<run_id>`: `manifest.json` and
   `inputs/RB-001.json` through `inputs/RB-012.json`
2. `renderer-b-expected-inputs-<run_id>`:
   `renderer-b-expected-inputs.yaml`

Use only an exact-head run issued **after** the clean-room contract,
declaration/schema and assignment synchronization. No prior challenge v0.2.0 or
custodian record with an old `starting_commit` can be treated as current.

## Execution gate — check actual byte identities and declaration

Only after the fresh isolated agent has committed its first implementation and
independently written tests, complete the implementation declaration and run:

```bash
python renderer_validation/validate_renderer_b_declaration.py \
  renderer-b-declaration.yaml \
  --expected-inputs renderer-b-expected-inputs.yaml \
  --challenge-dir renderer-b-development-challenge \
  --output renderer-b-exploratory-readiness.json
```

The standalone script checks **actual instances**, not only schemas: 12 case
identities, graph hashes, clean payloads, manifest hash, the real local
draft-contract byte hash, declaration/custodian field-by-field equality,
Codex AI-authorship disclosure and non-exposure. A result of
`ready_for_exploratory_agent_comparison: true` is **development-only**.

The script always reports `ready_for_differential_comparison: false` and
`scientific_independence_qualified: false` for this Codex-specific path.
It does not grant G1, human adjudication, manuscript confirmation,
protocol freeze or sealed tests.

## Isolation

Do not grant Codex unrestricted `protocol-v1` checkout, historical PR diffs,
Renderer A source/output, lifter, semantic verifier, fault labels, gold/answers
or sealed content. No external model receives licensed HL7 Edition 5 source
unless actual rights/hosting authorization is documented. See
`docs/renderer_b_assignment_packet.md` for the allowed implementation subset
and `CLEANROOM_README.md` for source restrictions.
