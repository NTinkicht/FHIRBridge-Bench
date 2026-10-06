# Clean-Room Assignment Packet — Renderer B

Status: **Implementation brief for an independent contributor**

## Objective

Implement **Renderer B** for the first FHIRBridge-Bench laboratory slice as an independent reference renderer.

Renderer B exists to provide **differential evidence about task specification and implementation ambiguity**. It is not ground truth. Agreement between Renderer A and Renderer B does not validate the canonical facts or projectability contract by itself.

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
4. Projectability contract `contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml`.
5. `docs/projectability_contract.md`.
6. `docs/target_profiles.md`.
7. `docs/field_mapping_audit_lab_oru_r01.md`.
8. Official HL7 FHIR R4 / US Core documentation.
9. Official HL7 v2.5.1 LRI Edition 5 and applicable errata/material.
10. Independent standards libraries/documentation selected by the implementer.

If the contract is ambiguous, do not infer Renderer A behavior. Record the ambiguity in a renderer disagreement note or propose that the rule remain `INDETERMINATE`.

## Required outputs

Renderer B should implement two independently authored projections for the currently frozen development slice:

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
- report-to-result and specimen relationships supported by the current canonical graph.

### Canonical → HL7 v2.5.1 ORU^R01

At minimum support the currently scoped LRI-oriented fields represented by the contract:

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
