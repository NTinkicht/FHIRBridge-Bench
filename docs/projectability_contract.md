# Projectability Contract Specification

Status: **Draft — Protocol v0.1**

## Purpose

The projectability contract defines what semantic preservation means for a specific source representation and a specific target implementation profile.

It is not a converter, not a gold serialization, and not an HL7 standard. It is a versioned study instrument that declares what information must survive, what transformations are licensed, what loss is acceptable, and what inference is forbidden.

## Contract scope

Every contract instance must name:

- source standard and version;
- source profile or scenario family;
- target standard and version;
- target message/resource profile;
- clinical scenario;
- terminology dependencies;
- applicable implementation assumptions;
- contract version.

## Required projectability classes

Each canonical fact or fact component is assigned one of:

### MUST_PRESERVE

The fact must remain represented with equivalent clinical meaning in the target.

Failure modes:

- omission;
- semantic corruption;
- misattribution.

### MAY_TRANSFORM

The fact may change representation only through an explicitly licensed transformation.

Examples:

- terminology translation;
- UCUM-equivalent unit conversion;
- normalization of date/time formatting;
- representation change between coded and target-profile-equivalent structures.

### MAY_LOSE

The target profile cannot reliably or appropriately represent the fact. Loss is permitted, but the contract must state the rationale.

Loss must never be silently reclassified after model outputs are observed.

### MUST_NOT_INFER

The target must not introduce a clinical fact unless it is explicitly grounded in the source or licensed by a declared derivation rule.

### INDETERMINATE

The research team and external reviewers cannot establish a sufficiently stable rule. These facts are excluded from the primary confirmatory endpoint and retained as an ambiguity set.

## Transformation operations

Permitted operations are closed and versioned. Draft operation types:

- `COPY`
- `NORMALIZE`
- `CODE_TRANSLATE`
- `UNIT_CONVERT`
- `AGGREGATE`
- `DECOMPOSE`
- `DERIVE_DECLARED`
- `DROP_DECLARED`

Any operation not present in the contract is unlicensed.

## Equivalence rules

The contract must specify how semantic equivalence is established for each fact class.

Examples:

- exact identity for patient identifiers unless a declared namespace transformation applies;
- terminology equivalence through an approved mapping source;
- UCUM-equivalent quantity conversion;
- tolerated timestamp precision changes where explicitly allowed;
- representation-independent relationship equivalence for references.

## Reverse-direction requirement

FHIR → HL7 v2 contracts must target a **named and versioned HL7 v2 implementation profile or message specification** whenever possible.

The study must not evaluate against a vague target of “valid HL7 v2.”

The contract must separately specify:

- target trigger event;
- required segments;
- segment repetition rules;
- field usage constraints;
- vocabulary/table expectations;
- treatment of extensions or FHIR-only structures;
- local-profile assumptions.

## Contract governance

Before confirmatory runs:

1. contract version is frozen;
2. every rule has provenance to a standards source, expert decision, or explicit study assumption;
3. external reviewers independently classify a sample of rules;
4. agreement statistics are reported;
5. unresolved disagreement is moved to `INDETERMINATE`;
6. post-freeze changes require a protocol amendment.

## Independence from generation

The contract may inform one explicitly defined mapping-aware generation arm, but this creates a contamination risk.

Safeguards:

- scoring must operate on canonical facts and declared equivalence classes, not target strings;
- model-prompt mappings cannot be the only evidence used by the verifier;
- held-out implementation variants must not be exposed in prompts;
- results should be stratified by mapping-source coverage when relevant.

## Contract record format

Each rule should minimally contain:

```yaml
rule_id: OBS_VALUE_001
scenario: laboratory_result
source_fact: observation.value
source_standard: FHIR_R4
source_profile: <named profile>
target_standard: HL7v2_2.5.1
target_profile: <named profile>
projectability: MUST_PRESERVE
allowed_operations:
  - COPY
  - UNIT_CONVERT
equivalence:
  type: quantity
  unit_system: UCUM
severity_if_failed: S2
rationale: <human-readable rationale>
evidence:
  - <standards/expert source>
status: draft
```

## Primary-endpoint eligibility

Only facts whose contract state is one of:

- `MUST_PRESERVE`
- `MAY_TRANSFORM`
- `MUST_NOT_INFER`

contribute directly to the primary fidelity endpoint.

`MAY_LOSE` is reported in the loss inventory.

`INDETERMINATE` is excluded from the primary endpoint and reported separately.

## Prohibited practice

The following are not allowed after the confirmatory experiment starts:

- changing a `MUST_PRESERVE` fact to `MAY_LOSE` because models fail on it;
- adding a licensed derivation after observing a model's unsupported output;
- changing severity thresholds to improve results;
- rewriting contract rules to align with one deterministic engine;
- silently deleting ambiguous cases.
