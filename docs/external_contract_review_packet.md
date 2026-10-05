# External Expert Review Packet — FHIRBridge-Bench Projectability Contract

Status: **Draft reviewer packet — required before Contract v1.0 freeze**

## Purpose

FHIRBridge-Bench is a measurement study of semantic fidelity in AI-mediated healthcare interoperability transformations. The project does **not** ask reviewers to judge an LLM, select a preferred converter, or define a new HL7 standard.

This review asks whether the study's proposed FHIR R4 → HL7 v2.5.1 laboratory **projectability contract** is a defensible measurement instrument for a deliberately narrow use case.

The contract must establish, before confirmatory model experiments, which source clinical facts:

- must survive transformation;
- may change representation under an explicitly licensed operation;
- may legitimately be lost because the selected target profile cannot represent them adequately;
- must not be inferred when absent from the source; or
- remain too ambiguous to score automatically.

Unresolved ambiguity is expected and should be labelled `INDETERMINATE`; reviewers should not force agreement where the standards evidence does not support it.

## Study scope to review

**Source**
- HL7 FHIR R4
- US Core 9.0.0 laboratory reporting
- US Core DiagnosticReport for Laboratory Results Reporting
- US Core Laboratory Result Observation
- US Core Patient
- FHIR Specimen where present

**Target**
- HL7 v2.5.1
- Laboratory Results Interface (LRI), Edition 5, US Realm
- 2024DEC errata
- ORU^R01

**Initial clinical slice**
- general chemistry / hematology-style laboratory reporting;
- atomic results;
- simple panels;
- patient, report, observation, and specimen facts represented by the frozen study schema.

Out of scope for the first confirmatory slice include microbiology susceptibility, genomics, newborn screening, unrestricted narrative reports, unreviewed local FHIR extensions, and arbitrary Z-segment conventions.

## Files forming the review record

Review against the following versioned artifacts on the `protocol-v1` branch:

1. `contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml` — proposed machine-readable rules.
2. `docs/field_mapping_audit_lab_oru_r01.md` — field-level evidence ledger and unresolved mappings.
3. `docs/contract_review_protocol.md` — independence, agreement, adjudication, and freeze procedure.
4. `docs/projectability_contract.md` — construct-level projectability definitions.
5. `canonical/schema/` — canonical fact definitions where a rule's source semantics require clarification.

The official HL7 v2→FHIR mappings are evidence of semantic correspondence only. They must **not** be treated as proof that the reverse mapping is unique, lossless, or automatically valid for this target profile.

## Reviewer independence

Please make your initial classifications independently.

During initial review, do **not** use:

- outputs from any LLM evaluated in this project;
- outputs from Renderer A or Renderer B as correctness evidence;
- the study verifier's classifications;
- Microsoft, CDC PRIME, LinuxForHealth, or another converter output as ground truth.

External converters may later be used for differential disagreement analysis, but converter agreement does not establish truth.

## Required decision for every scored rule

Choose exactly one projectability state:

### `MUST_PRESERVE`
The source fact is in scope and its clinical meaning must survive in the selected v2 target profile. Missing required information is an omission.

### `MAY_TRANSFORM`
The fact must survive semantically, but one or more listed representation changes are permissible. Review the allowed operation list as part of this decision.

### `MAY_LOSE`
The fact is in scope at the FHIR source but can legitimately be unrepresented under the named target profile. This classification requires a specific standards/profile rationale; it must not be used simply because reverse mapping is inconvenient.

### `MUST_NOT_INFER`
The target must not assert the fact unless it is grounded in the source or in an explicitly licensed derivation rule.

### `INDETERMINATE`
The evidence, implementation profile, or competing legitimate representations are insufficient to support a stable primary-endpoint rule.

## Allowed-operation review

For rules classified `MAY_TRANSFORM`, separately indicate whether each proposed operation is acceptable:

- `COPY`
- `NORMALIZE`
- `CODE_TRANSLATE`
- `UNIT_CONVERT`
- `AGGREGATE`
- `DECOMPOSE`
- `DERIVE_DECLARED`
- `DROP_DECLARED`

An operation should be accepted only when semantic equivalence is defensible under the named profiles and the rule states enough constraints to prevent clinically meaningful drift.

## Rule-review form

Complete one row per rule. Preserve your initial decision before adjudication.

| Field | Reviewer response |
|---|---|
| Reviewer ID | |
| Rule ID | |
| Proposed canonical fact | |
| Independent projectability decision | MUST_PRESERVE / MAY_TRANSFORM / MAY_LOSE / MUST_NOT_INFER / INDETERMINATE |
| Proposed target locus defensible? | Yes / No / Partly / Indeterminate |
| Alternative legal target locus? | None / specify |
| Allowed operations accepted | list |
| Allowed operations rejected | list + reason |
| Equivalence rule adequate? | Yes / No / Partly |
| Severity assignment plausible? | Yes / No / Not qualified to judge |
| Evidence sufficient? | Yes / No / Partly |
| Evidence or standard section relied on | citation/section |
| Main concern | free text |
| Confidence | High / Moderate / Low |

## Core rules requiring explicit review

At minimum, independently review the current candidate rules for:

### Patient / PID
- patient identifier → PID-3;
- patient name → PID-5;
- patient birth date → PID-7.

### DiagnosticReport / OBR
- report/order code → OBR-4;
- effective start/end → OBR-7 / OBR-8;
- issued/released time → OBR-22;
- report status → OBR-25.

### Observation / OBX
- observation code → OBX-3;
- typed observation value → OBX-5, interpreted jointly with OBX-2;
- unit → OBX-6 with value-unit joint equivalence;
- reference range → OBX-7;
- interpretation → OBX-8;
- result status → OBX-11;
- observation effective time → OBX-14.

### Specimen / SPM
- specimen identifier → SPM-2;
- specimen type → SPM-4;
- collection method → SPM-7;
- collection quantity → SPM-12;
- collection time → SPM-17.

### Forbidden unsupported assertions
- source-free clinical assertions derived from report/note/narrative content when no licensed source grounding exists.

## Questions that must be answered explicitly

1. For each `MUST_PRESERVE` rule, is the target location legal and semantically appropriate under the selected LRI profile?
2. For each `MAY_TRANSFORM` rule, are all listed operations truly semantics-preserving under the constraints written in the contract?
3. Are any current rules overly strong and better classified `INDETERMINATE`?
4. Are any in-scope source facts missing from the core contract such that omission measurement would be biased?
5. Are any current `MUST_PRESERVE` or `MAY_TRANSFORM` facts actually defensible `MAY_LOSE` cases? If yes, identify the exact target-profile reason.
6. Do any source facts have multiple equally valid v2 target loci that require an equivalence class rather than one expected field?
7. Are patient, report, observation, and specimen identifier semantics sufficiently separated, or does any rule collapse distinct business identifiers?
8. Are temporal precision and timezone normalization rules sufficiently constrained?
9. Are code equivalence and UCUM conversion rules conservative enough to prevent broader/narrower concept substitutions from being counted as equivalent?
10. Which rules, if any, should remain `INDETERMINATE` for the primary endpoint even after adjudication?

## Known unresolved items

The study currently treats the following as unresolved rather than guessing:

- DiagnosticReport identifiers versus v2 placer/filler/order identifiers;
- encounter context;
- performer/results-interpreter representation;
- panel/component topology and OBX-4/group semantics;
- unrestricted free text and presentation forms;
- local extensions and Z-segments.

Please state whether any of these can be safely promoted into the scored core for the selected profile. There is no requirement to do so.

## Agreement and adjudication

Two external reviewers should complete the initial review independently. The project will retain and report both original decisions before adjudication.

Planned reporting:

- raw agreement;
- Cohen's kappa where appropriate;
- Gwet's AC1 as a prevalence-robust companion;
- projectability-class confusion matrix;
- qualitative disagreement reasons.

A third expert may adjudicate disagreements. If a stable standards-based decision cannot be reached, the final rule remains `INDETERMINATE` and is excluded from the primary endpoint.

## Freeze rule

Contract v1.0 will not be frozen until:

- every primary-endpoint rule has a standards/expert evidence record;
- the independent review is complete;
- agreement statistics are archived;
- disputed rules are adjudicated or marked `INDETERMINATE`;
- any rule changed after renderer disagreement is re-reviewed;
- the reviewed contract and decision record are versioned and tagged.

After confirmatory model runs begin, no rule may be weakened because a model performs poorly. Any post-freeze change requires a protocol amendment and, where possible, analysis under both the original and amended contracts.

## Reviewer attestation

Please confirm:

- I completed my initial rule classifications independently.
- I did not use study model outputs or verifier outputs to determine correctness.
- I understand that I am reviewing a scoped study instrument, not endorsing a universal FHIR→HL7 v2 mapping standard.
- I have declared any relevant conflict of interest or project involvement.

Reviewer ID: ____________________

Relevant expertise: ____________________

Date: ____________________

Signature/confirmation: ____________________
