# Clean-Room Assignment Packet — Renderer B

Status: **Implementation brief for an independent contributor**

## Objective

Implement **Renderer B** for the first FHIRBridge-Bench laboratory slice as an independent reference renderer.

Renderer B exists to provide **differential evidence about task specification and implementation ambiguity**. It is not ground truth. Agreement between Renderer A and Renderer B does not validate the canonical facts or projectability contract by itself.

## AI-authored agent B status (2026-10-18; pre-freeze)

The PI has chosen **Codex** to develop an *exploratory* Renderer B prototype.
Codex is an LLM coding agent, so mapping code it generates must be declared
truthfully with `independence.llm_generated_mapping_code_used: true`.
The current scientific clean-room protocol explicitly prohibits LLM-generated
mapping code. **This agent-authored prototype cannot pass the existing
`ready_for_differential_comparison` scientific intake gate** by obtaining
green CI, matching challenge hashes, or providing a declaration.

The coordinator's declaration checker now exposes a separate,
nonauthoritative `ready_for_exploratory_agent_comparison` diagnostic if the
only blocker is precisely the disclosed AI authorship. All other isolation,
custody, source-identity, and exposure checks still apply. Any comparative
results from this route must be labeled *exploratory development diagnostics*;
they do not clear scientific independence, contract review, G1 conformance,
or protocol freeze. The CLI intentionally exits nonzero when the scientific
comparison gate remains blocked.

A future route that seeks to use an AI-authored Renderer B as scientifically
accepted independent evidence requires a **prospective methodology amendment
and independent technical assessment**, not a silent change of the current
rules. Never mark the LLM-generated field `false` for a Codex-authored mapping
or reuse Renderer A's implementation/outputs to improve B before first lock.

## Independence requirement

The implementer of Renderer B must not inspect, copy, refactor, or mechanically translate Renderer A source code before completing the initial implementation and test set.

Do **not** read:

- `src/fhirbridge/renderers/fhir_r4_a.py`
- `src/fhirbridge/renderers/hl7v251_oru_a.py`
- Renderer-A-specific test expectations beyond public interface contracts
- Renderer A commit diffs or implementation commentary

The implementer may use only the materials explicitly listed below during the clean-room phase.

## Authoritative inputs permitted during implementation

1. Canonical fact schema under `canonical/schema/`.
2. Canonical development examples under `canonical/examples/`.
3. Scenario definitions under `benchmark/`.
4. Projectability contract `contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml`.
5. `docs/projectability_contract.md`.
6. `docs/target_profiles.md`.
7. `docs/field_mapping_audit_lab_oru_r01.md`.
8. Official HL7 FHIR R4 / US Core documentation.
9. Official HL7 v2.5.1 LRI Edition 5 and applicable errata/material.
10. Independent standards libraries/documentation selected by the implementer.

If the contract is ambiguous, do not infer Renderer A behavior. Record the ambiguity in a renderer disagreement note or propose that the rule remain `INDETERMINATE`.

## Clean-room development challenge package

Before implementation begins, generate the shared development input package with:

```bash
python renderer_validation/build_renderer_b_challenge.py
```

The project custodian must also generate and retain a schema-valid expected-input
record with `renderer_validation/build_renderer_b_expected_inputs.py`. That
record pins the exact `renderer-b-cleanroom` starting commit, challenge
manifest SHA-256, and contract SHA-256. The implementer copies the
`clean_room_inputs` block verbatim into the final declaration; it is input
identity, not an independence claim.


### Enforced challenge-content preflight

The challenge generator validates the **actual canonical graph contents**
before it writes any handoff files. It fails closed on non-development or
non-synthetic cases, mismatched graph hashes, duplicate case/graph identities,
or nested source/reference-output fields (Renderer A output, gold target
serializations, verifier decisions, fault labels, sealed cases and answer keys).
The manifest flags alone are **not** accepted as evidence that these
sensitive outputs are absent.

The sanitized challenge package is now **v0.3.0** (a breaking change to
v0.2.0) because internal canonical test `assertions` with expected
values and units have been stripped from the exported graph **before hashing**.
The custodian must regenerate the entire 12-case package and handoff record;
older v0.2.0 manifests and contract hashes must not be treated as equivalent
to the new input identity. Any existing Codex session exposed to v0.2.0
assertions cannot retroactively be called blind.

The resulting sanitized challenge may be passed to an isolated Codex
development session **only after** its exact handoff hashes and permitted-file
boundary are recorded. Do not give Codex broader access to `protocol-v1`,
unrestricted GitHub search, Renderer A PR diffs or any source/verifier/gold
content not explicitly allowlisted. A passing exposure check reduces
accidental leakage; it does **not** prove agent isolation, implementation
independence or normative accuracy. Codex mapping code must still be reported
as AI-authored exploratory work.

The package contains one deterministic canonical development graph for each
`LAB-001` through `LAB-012`, plus a manifest with graph hashes. The v0.3
challenge now includes one source-grounded canonical `order` fact per case and
explicit report-to-order linkage. It explicitly contains **no Renderer A output,
no target gold serialization, no verifier decisions, and no fault labels**. The package is therefore safe to
share with the independent implementer without exposing the reference
implementation.

`LAB-012` remains included as an ambiguity/unsupported-behavior challenge and
is marked non-primary / `INDETERMINATE`; it must not be forced into a
serialization merely to maximize scenario coverage.

## Required outputs

Renderer B should independently implement the currently reviewable projections below. Contract v0.3 remains a **draft synchronization point**, not frozen semantic truth:

### Canonical → FHIR R4

At minimum support the in-scope facts needed for:

- Patient;
- DiagnosticReport;
- Observation;
- Specimen;
- identifiers;
- result/report codes;
- observation value + unit;
- status;
- effective/issued/collection times;
- reference range;
- interpretation;
- report-to-result and specimen relationships supported by the current canonical graph;
- source-grounded ServiceRequest order context;
- `DiagnosticReport.basedOn` linkage to the originating ServiceRequest.

### Canonical → HL7 v2.5.1 ORU^R01

For the legacy/order-free development subset, support the currently scoped fields represented by the contract:

- PID-3 patient identifier;
- PID-5 patient name;
- PID-7 date of birth;
- OBR-4 report/order code;
- OBR-7 / OBR-8 report effective interval where applicable;
- OBR-22 issued/released time;
- OBR-25 report status;
- OBX-2 value type;
- OBX-3 observation code;
- OBX-5 observation value;
- OBX-6 units;
- OBX-7 reference range;
- OBX-8 interpretation;
- OBX-11 result status;
- OBX-14 observation effective time;
- current SPM identifier/type/collection fields covered by the contract.

**Do not invent or silently infer the v0.3 Edition 5 order projection.** The challenge inputs contain order context so Renderer B can demonstrate explicit unsupported/fail-closed behavior. Until the exact Edition 5 machine-readable profile is acquired and the blind external review resolves the remaining order-locus questions, Renderer B must not claim a frozen mapping for MSH-21, ORC-1, ORC-3, ORC-12, OBR-3, OBR-16, or related datatype/binding constraints.

The current development slice intentionally uses a single OBR group. Do not silently extend the scientific scope to multi-OBR or multi-specimen attribution unless that extension is separately reviewed and versioned.

## Technical independence

Use a meaningfully different implementation route from Renderer A where practical. Examples:

- different programming language; or
- different standards library; or
- different internal data-construction approach.

If operational constraints require the same language, document why the implementation remains independently authored and which libraries/algorithms differ.

Do not share helper functions with Renderer A except truly generic repository utilities that contain no mapping/serialization decisions.

## Renderer contract

Renderer B must:

- accept canonical graph input without mutating it;
- accept the frozen contract/profile metadata explicitly rather than reading hidden global state;
- emit deterministic output for a fixed input/version/configuration;
- record renderer implementation/version metadata;
- fail explicitly on unsupported/indeterminate facts instead of inventing mappings;
- treat the current HL7 v2 order-context projection as unsupported until a synchronized contract/profile amendment explicitly releases it;
- preserve synthetic identifiers and timestamps according to the contract;
- never call the semantic verifier to decide how to render content.

The renderer must not use verifier classifications, fault manifests, model outputs, or Renderer A output as generation input.

## Testing requirements before comparison with Renderer A

The independent implementer should complete tests without seeing Renderer A output.

Required test families:

1. deterministic repeated rendering;
2. no mutation of canonical input;
3. syntactic parseability of emitted FHIR/HL7 artifacts;
4. in-scope scenario coverage;
5. explicit failure/indeterminate behavior for unsupported facts;
6. unit/value and code-system preservation;
7. identifier namespace handling;
8. temporal precision/offset handling;
9. relationship preservation within the currently supported topology;
10. locally authored golden examples derived directly from the standards/contract, not copied from Renderer A.

## Independence declaration

Before differential comparison, the implementer must record:

- contributor/agent identity;
- implementation start/end date;
- source commit from which work began;
- languages/libraries used;
- standards/profile documents consulted;
- confirmation that Renderer A source/output was not inspected during initial implementation;
- any accidental exposure or unavoidable shared utility;
- known unsupported cases.

The declaration must validate against:

- `renderer_validation/schema/renderer_implementation_declaration.schema.json`

Differential comparison additionally requires the custodian's original handoff
record, validated against
`renderer_validation/schema/renderer_b_expected_inputs.schema.json`. Run:

```bash
python renderer_validation/validate_renderer_b_declaration.py \
  renderer-b-declaration.yaml \
  --expected-inputs renderer-b-expected-inputs.yaml
```

A mismatch in starting commit, challenge hash, or contract hash blocks the
comparison.

A non-assertive completion template is provided at:

- `renderer_validation/examples/renderer_b_declaration_template.yaml`

The template is not an independence claim. The independent implementer must replace all placeholders, record any exposure truthfully, and set `declaration_complete: true` only after the initial clean-room implementation and tests have been committed.

## Differential comparison phase

Only after Renderer B's implementation and initial tests are committed may the two renderers be compared.

For every disagreement, record:

- canonical scenario/fact(s);
- Renderer A output locus/value;
- Renderer B output locus/value;
- applicable contract rule;
- whether both outputs are legal equivalents;
- whether one implementation violates the frozen rule/profile;
- whether the contract is underspecified;
- adjudication decision;
- whether the affected rule must become `INDETERMINATE` or receive an amendment before freeze.

Each differential record must validate against:

- `renderer_validation/schema/renderer_disagreement.schema.json`

The controlled vocabulary intentionally forbids majority-vote resolution and preserves `CONTRACT_AMBIGUITY` and `INDETERMINATE` as explicit outcomes. An external converter can be recorded only as a comparator and the schema requires `used_as_ground_truth: false`.

Do not silently modify Renderer B to match Renderer A.

## External converter use

After clean-room implementation, one or more external converters may be used as **differential oracles**. Their output is comparison evidence only and must not be promoted to ground truth.

## Completion gate

Renderer B is considered ready for the Protocol v1.0 freeze only when:

- independence declaration is archived and schema-valid;
- supported scenario tests pass;
- structural/profile validation is documented;
- differential comparison is complete on the development scenario set;
- every substantive disagreement is logged in a schema-valid record and adjudicated;
- no contract rule is changed merely to make the two implementations agree;
- any unresolved standards ambiguity is marked `INDETERMINATE` for the primary endpoint.
