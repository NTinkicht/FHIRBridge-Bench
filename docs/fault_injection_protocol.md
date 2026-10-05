# Fault Injection Protocol

Status: **development protocol, not frozen**

This document defines how FHIRBridge-Bench creates qualification stimuli for the semantic verifier. Seeded faults are measurement-instrument tests, not substitutes for expert-adjudicated validation and not ground truth for naturally occurring LLM errors.

## 1. Purpose

The fault suite asks whether the verifier detects known, controlled semantic and structural defects while avoiding double counting and false positives. It supports three goals:

1. estimate detector behavior by error class and severity;
2. expose blind spots before the verifier is frozen;
3. provide regression fixtures after taxonomy or contract decisions are adjudicated.

The suite must not be used to tune the verifier on the sealed expert-validation set.

## 2. Two injection levels

FHIRBridge-Bench uses two explicitly different mutation levels.

### 2.1 Canonical-level semantic injection

Use canonical-level injection when the intended error is intrinsic to the clinical fact itself and should survive any faithful target rendering.

Examples include:

- unsupported observation fabrication;
- numeric value mutation;
- unit mutation without joint conversion;
- terminology mutation;
- identifier mutation;
- temporal mutation;
- status, interpretation, and reference-range mutation;
- required clinical-fact omission.

Canonical operators live in `src/fhirbridge/faults.py`. They deep-copy the source graph and must not import renderer, lifter, or verifier decision logic.

### 2.2 Target-artifact-level injection

Use artifact-level injection when the relevant error exists only in target message/resource structure or when canonical re-rendering would erase the intended defect.

This is necessary because some standards carry context at group, segment, message, or reference level rather than redundantly on every canonical fact. A canonical mutation can therefore disappear during a deterministic rendering step.

Examples include:

- removing a required target field from an otherwise parseable message;
- inserting an unsupported derived OBX into an otherwise structurally acceptable ORU;
- corrupting a message/profile discriminator as a structural negative control;
- future group-level report/observation or specimen misattribution cases.

Artifact operators live in `src/fhirbridge/artifact_faults.py` and must not import semantic-verifier decision logic.

## 3. Structural validity is a separate axis

Every fault stimulus declares an expected structural-validity state independently of the semantic error class.

A semantic fault may be intentionally **structurally valid**. These cases are especially important because they instantiate the paper's central construct: a target artifact can satisfy syntax/profile gates while failing source-grounded semantic fidelity.

Structural-only negative controls, such as F018, are intercepted by the structural-validation layer and are not counted as semantic-fidelity failures.

The current `Hl7V251OruDevelopmentValidator` is a development sanity gate only. It is not evidence of full LRI Edition 5 conformance. Confirmatory experiments require an independently documented profile-level validation path.

## 4. Error taxonomy and precedence

The current semantic precedence is:

`MISATTRIBUTION > CORRUPTION > OMISSION > FABRICATION`

This order prevents a single defect from being counted as multiple independent failures when the stronger explanation subsumes the weaker ones.

Examples:

- a correctly grounded observation attached to the wrong patient is MISATTRIBUTION, not an omission from one patient plus fabrication for another;
- an absent required projectable field is OMISSION, not generic corruption;
- an extra unsupported target clinical assertion is FABRICATION.

`INDETERMINATE` is used when the contract or verifier cannot defensibly resolve a case. It is preferable to forced classification.

## 5. Projectability-aware omission

Whole-fact absence and field-level absence are both possible omissions.

For a grounded fact, a source field is classified as field-level OMISSION only when:

1. the source assertion is present;
2. the corresponding target assertion is absent rather than merely different;
3. the compiled projectability contract marks that field as `MUST_PRESERVE` or `MAY_TRANSFORM`;
4. the field participates in the frozen semantic comparison policy.

A present-but-different value remains CORRUPTION unless a more specific higher-precedence class applies.

Fields marked `MAY_LOSE` require declared-loss handling and are not converted automatically into omission failures. Fields excluded as `INDETERMINATE` are not confirmatory endpoints.

## 6. Current fault inventory

The canonical suite currently covers F001, F002, F003, F004, F005, F006, F008, F010, F011, F012, F013, and F015.

The target-artifact suite currently covers:

- **F009**: report issued-time omission at OBR-22;
- **F016**: unauthorized derived assertion as an unsupported OBX;
- **F018**: structural negative control by invalidating MSH-12.

Still pending are representation-aware implementations for F007 and F014, explicit declared-loss testing for F017, and the multi-fault templates.

## 7. Qualification workflow

For semantic faults expected to remain structurally valid:

1. generate an untouched canonical source case;
2. apply the specified canonical or artifact mutation at the declared mutation level;
3. render if the mutation occurred at canonical level;
4. run the structural gate and record its verdict;
5. independently lift the target artifact;
6. compile the versioned projectability policy;
7. run semantic grounding and classification;
8. compare the verifier result with the prespecified mutation label;
9. persist evidence and run-manifest metadata.

For structural negative controls, semantic scoring stops when the structural gate fails unless an explicitly separate diagnostic analysis has been preregistered.

## 8. Required run-manifest fields

Each generated qualification stimulus must eventually record at least:

- source scenario ID and seed;
- source canonical-generator version;
- target profile and renderer version;
- projectability contract ID/version;
- mutation level: `canonical` or `target_artifact`;
- fault ID and operator version;
- expected primary class;
- expected severity;
- expected structural-validity state;
- mutated source/target locator where applicable;
- lifter version;
- structural validator/version;
- verifier version/frozen hash;
- terminology/UCUM dependency versions;
- observed verifier class and evidence;
- whether the stimulus belongs to development, pilot, or sealed confirmatory qualification.

## 9. Independence safeguards

Fault generators may know the taxonomy and the projectability contract, but they must not call verifier classification functions to decide how to mutate an artifact.

The verifier may know the frozen contract but must not inspect a mutation's expected label during scoring.

Confirmatory seeded faults should include a subset authored or reviewed by a person who has not inspected the verifier implementation details. The sealed expert-validation set remains independent of this seeded suite.

## 10. Pilot and confirmatory planning targets

Current planning targets, subject to statistical justification before freeze, are:

- at least 50 single-fault stimuli per primary semantic class during development/pilot qualification;
- at least 25 confirmatory stimuli per primary class authored or independently reviewed blind to verifier implementation details;
- at least 100 multi-fault stimuli to test precedence and compound-error behavior.

These are planning targets rather than claims that those exact counts are statistically sufficient. Final sample sizes must be justified in the analysis plan.

## 11. Freeze rule

Before opening the sealed expert-validation set, freeze:

- taxonomy and class definitions;
- severity definitions;
- precedence rules;
- projectability contract version used for confirmatory scoring;
- mutation operator semantics;
- verifier classification policy;
- the distinction between canonical-level and artifact-level injection.

After freeze, any material change requires a new version and an explicit sensitivity analysis rather than silently modifying the instrument.
