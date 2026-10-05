# Renderer B Clean-Room Workspace

This branch is an intentionally isolated implementation workspace for the independent **Renderer B** reference implementation used by FHIRBridge-Bench.

## Scientific purpose

Renderer B is not ground truth. It exists to provide an independently authored rendering path so that agreement/disagreement between implementations can reveal specification ambiguity and implementation-specific assumptions.

## Snapshot provenance

The permitted scientific inputs in this branch were copied from `protocol-v1` at the clean-room preparation snapshot associated with commit `46ebc48eeb4bbe765a9baa1491276cccdcd9dbe4` or earlier source blobs. The branch itself was created from `main` specifically to avoid exposing Renderer A, lifter, verifier, fault-injection, model, or experiment implementation code.

## Permitted implementation inputs

Use only the files present in this branch plus official standards/profile documentation and independently selected standards libraries.

The supplied study inputs are:

- `docs/renderer_b_assignment_packet.md`
- `docs/projectability_contract.md`
- `docs/target_profiles.md`
- `docs/field_mapping_audit_lab_oru_r01.md`
- `docs/standards_evidence_snapshot_2026-10-03.md`
- `contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml`
- `canonical/schema/clinical_fact.schema.yaml`
- `canonical/schema/clinical_fact_graph.schema.yaml`
- `canonical/examples/LAB-001-example.yaml`
- `benchmark/scenarios/lab_core_v0.1.yaml`

## Prohibited during initial clean-room implementation

Do not inspect other branches or commits containing:

- Renderer A source or output;
- lifters/parsers used by the study evaluator;
- verifier implementation or classifications;
- seeded-fault implementation;
- LLM prompts, model outputs, or experiment results;
- Renderer-A-specific tests or diffs.

In particular, do not read `protocol-v1` implementation directories under `src/fhirbridge/renderers`, `src/fhirbridge/lifters`, or `src/fhirbridge/verifier` until the initial Renderer B implementation and its independent tests are committed.

## Required independence record

Before differential comparison with Renderer A, create `INDEPENDENCE_DECLARATION.md` recording:

- implementer identity;
- implementation start/end dates;
- starting branch/commit;
- programming language and libraries;
- standards/profile documents consulted;
- confirmation that Renderer A source/output was not inspected;
- any accidental exposure or shared utility;
- known unsupported cases.

## Comparison gate

Only after Renderer B and its own tests are committed should a separate comparison phase expose Renderer A output. Do not silently change Renderer B merely to match Renderer A. Any substantive disagreement must be logged and adjudicated against the frozen contract and standards evidence; unresolved legitimate ambiguity becomes an equivalence class or `INDETERMINATE` rather than forced agreement.
