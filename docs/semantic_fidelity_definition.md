# Semantic Fidelity Definition

Status: **Draft — Protocol v0.1**

## Construct

**Semantic fidelity** is the preservation of source clinical facts under a declared projectability contract and declared equivalence rules.

A transformation is not considered faithful merely because it is syntactically valid or profile-conformant.

## Unit of evaluation

The primary unit is a **canonical clinical fact**, not a serialized field string.

A fact consists of:

- a fact type;
- subject / patient linkage;
- encounter or event context where applicable;
- coded concept where applicable;
- value;
- unit;
- temporal context;
- identifiers;
- references / relationships;
- provenance to the originating scenario.

## Projectability states

Each fact or fact component must be assigned exactly one primary projectability state for a named target profile:

- `MUST_PRESERVE`
- `MAY_TRANSFORM`
- `MAY_LOSE`
- `MUST_NOT_INFER`
- `INDETERMINATE`

`INDETERMINATE` is excluded from the confirmatory primary endpoint.

## Error classes

### 1. Fabrication / translation hallucination

Target clinical content for which no source fact or licensed derivation provides permissible grounding.

Examples:

- invented diagnosis;
- unsupported observation value;
- fabricated identifier;
- invented abnormal flag;
- fabricated code not licensed by terminology mapping.

### 2. Semantic corruption

Target content is grounded in a real source fact but changes its meaning.

Subtypes include:

- value corruption;
- terminology/code corruption;
- unit corruption;
- identifier corruption;
- reference/relationship corruption;
- temporal corruption;
- context corruption;
- misattribution to the wrong patient, encounter, order, observation, or performer.

### 3. Omission

A `MUST_PRESERVE` source fact has no semantically equivalent target representation.

### 4. Licensed normalization

A representation change explicitly allowed by the equivalence rules, such as:

- date/time formatting normalization;
- boolean representation changes;
- text casing where semantics are unaffected;
- canonical identifier formatting.

This is not an error.

### 5. Licensed derivation

A transformation explicitly permitted by the contract, such as:

- terminology translation through an approved map;
- UCUM-equivalent unit conversion;
- deterministic derivation of a required target representation.

This is not an error.

### 6. Declared representational loss

A fact marked `MAY_LOSE` is omitted and the loss is explicitly declared by the transformation or evaluation harness.

This is not a primary semantic-fidelity error, but silent loss may be reported separately.

### 7. Indeterminate

The mapping cannot be adjudicated reliably under the frozen contract or experts disagree materially about acceptable representation.

Indeterminate facts are excluded from the primary endpoint and reported separately.

## Error precedence

To avoid double counting, the verifier applies the following precedence order:

1. **Misattribution / relationship corruption**
2. **Semantic corruption**
3. **Fabrication**
4. **Omission**

A single target defect should not automatically generate multiple headline errors when one higher-precedence class explains the failure.

Example: a correct laboratory value attached to the wrong patient is counted as misattribution/corruption, not simultaneously as a clean value plus separate fabrication and omission events.

## Severity axis

Severity is independent of error type.

Draft levels:

- `S0` — benign / representational only
- `S1` — interoperability-relevant but unlikely to change clinical interpretation
- `S2` — clinically meaningful semantic change
- `S3` — potentially safety-critical semantic change

Severity rules require expert calibration before Protocol v1.0.

## Primary transformation-level event

A transformation is **unfaithful** for the primary endpoint when it contains at least one error meeting the pre-registered major-severity threshold among:

- fabrication;
- semantic corruption;
- required omission.

The primary study will define the exact severity threshold before confirmatory runs.

## Valid-but-Unfaithful Rate

Let:

- `V = 1` if the transformation passes the specified structural/profile validator;
- `F = 1` if the transformation contains at least one major semantic-fidelity error.

Then:

`VUR = P(F = 1 | V = 1)`

The primary stratum is FHIR → HL7 v2.

## Supporting rates

### Fabrication Rate

Unsupported target clinical facts / all emitted target clinical facts eligible for semantic scoring.

### Required Omission Rate

Missing `MUST_PRESERVE` facts / all `MUST_PRESERVE` facts.

### Semantic Corruption Rate

Corrupted grounded facts / all grounded facts eligible for corruption scoring.

### Structural Validity Rate

Validator-passing transformations / all attempted transformations.

## Provenance distinction

The study distinguishes:

- **claimed provenance** — grounding emitted by the model;
- **verified provenance** — grounding independently established by the verifier.

A model receives no semantic-fidelity credit solely for emitting a plausible source path.

## Non-goals

This construct does not claim:

- clinical safety;
- clinical truth beyond the benchmark's source facts;
- universal equivalence between HL7 v2 and FHIR;
- lossless round-trip conversion;
- that a single semantic contract is a replacement for an HL7 implementation guide.
