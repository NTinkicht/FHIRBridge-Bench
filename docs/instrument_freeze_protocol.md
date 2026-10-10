# Instrument and Sealed-Set Freeze Protocol — Draft v0.1

Status: **Draft — operational gate to be completed after pilot calibration and external review**

## Purpose

This protocol prevents the sealed expert-validation set from becoming part of verifier development.

A schema-valid record alone does not authorize unsealing. Before the first sealed case is opened, the repository must contain a completed, machine-readable freeze manifest that identifies the exact measurement instrument, dependencies, blinding controls, preregistered acceptance gate, and sealed-set bundle.

The manifest schema is:

- `expert_validation/schema/freeze_manifest.schema.json`

A deliberately incomplete template is:

- `expert_validation/examples/freeze_manifest_template.yaml`

The template is not a claim that the instrument is frozen. It contains placeholder hashes and `freeze_complete: false` until the scientific gates are actually satisfied.

## What must be frozen

The manifest records immutable identity and SHA-256 evidence for at least:

1. projectability contract;
2. semantic verifier;
3. FHIR lifter;
4. HL7 v2 lifter;
5. canonical clinical fact graph schema;
6. severity policy/rubric;
7. error-precedence policy.

The repository commit and protocol version are recorded separately so the exact research state can be reconstructed.

## Measurement-critical dependencies

The freeze record must pin the versions/sources used for:

- terminology equivalence;
- UCUM/unit equivalence;
- FHIR structural/profile validation;
- HL7 v2 structural/profile validation.

Additional parsing/statistical dependencies may also be recorded. A dependency may include a content hash where a fixed local snapshot exists.

Unpinned terminology or validation services are not acceptable for confirmatory measurement because their behavior can change independently of the repository commit.

## Sealed-set identity

Before opening, record:

- split = `sealed_test`;
- sealed bundle identifier;
- bundle SHA-256;
- case-manifest SHA-256;
- final case count;
- sampling/enrichment notes and weighting-plan reference where applicable.

Before the first opening:

- `opened` must remain false;
- `opened_at` must remain null;
- `opened_by_role_ids` must remain empty.

Opening is a one-way governance event. A post-unsealing measurement change cannot be disguised as an ordinary code fix.

## Blinding record

The manifest records pseudonymous role identifiers rather than requiring names in the public artifact.

At minimum, the sealed validation workflow must have roles covering:

- primary interoperability reviewer;
- primary clinical-informatics reviewer;
- adjudicator;
- data custodian.

The manifest also explicitly records that primary reviewers remain blinded to:

- model identity;
- generation strategy;
- verifier verdict;
- claimed model provenance;
- the other primary reviewer's labels.

`controls_verified: true` may be set only after the actual review package has been checked, not merely because the protocol intends to blind those fields.

## Acceptance gate

The numerical instrument acceptance gate is intentionally **not hard-coded in software**.

After pilot calibration and before opening the sealed set, the preregistration must define:

- which performance quantities gate confirmatory use;
- their pilot-derived thresholds;
- whether point estimates, confidence-bound criteria, or both are used;
- how indeterminate cases are handled;
- any multiplicity or stratification rule relevant to the gate.

The freeze manifest records the preregistration reference and hash and attests whether the gate was defined before sealed opening.

The threshold-setting procedure itself is now preregistered in
`benchmark/pilot_acceptance_plan.yaml`. After pilot adjudication, the concrete
numeric gate must be recorded in a schema-valid
`pilot_acceptance_preregistration` record before any sealed case is opened.
The record binds the pilot case/adjudication hashes, frozen verifier and
contract hashes, Wilson 95% confidence intervals, selected sensitivity/PPV
statistics, numeric thresholds, rationales, and an explicit attestation that no
sealed results were used. The deliberately incomplete repository template is
not freeze-ready.

## Automated pre-opening audit

`src/fhirbridge/freeze_audit.py` implements a conservative readiness check after schema validation.

It blocks sealed-set opening when, among other things:

- the freeze is not marked complete;
- freeze timestamp or protocol version is not finalized;
- measurement components retain placeholder versions/paths/hashes;
- required terminology/UCUM/FHIR/v2 validation dependencies are not pinned;
- the sealed bundle has zero/placeholder hashes or no cases;
- the sealed set is already marked opened;
- required blinding controls/roles are missing;
- the pilot-derived acceptance gate has not been preregistered.

The readiness audit does not prove scientific validity and does not replace independent review. Its purpose is to make accidental premature unsealing or silent instrument drift harder.

## Post-freeze amendments

Every amendment after freeze is recorded in the manifest with:

- amendment identifier/time;
- reason;
- affected components;
- whether the sealed set had already been opened;
- whether a fresh sealed set is required;
- disposition.

Allowed dispositions are deliberately limited to:

- `NO_EFFECT_ON_FROZEN_MEASUREMENT`;
- `REQUIRES_NEW_SEALED_SET`;
- `DOWNGRADE_TO_EXPLORATORY`.

There is no "ignore and continue" path for a material post-unsealing instrument change.

If verifier logic, lifter logic, contract rules, severity anchors, precedence rules, or acceptance thresholds are changed after sealed opening, the conservative default is a **fresh untouched sealed set**. If that is not feasible, results using the revised instrument are explicitly exploratory.

## Relationship to seeded faults

Seeded-fault qualification may be run before the sealed expert set is opened and is part of instrument development evidence.

It does not authorize unsealing by itself and does not substitute for naturally occurring model-output adjudication.

## Relationship to Renderer B and contract review

The freeze cannot be completed until the projectability contract has passed its independent-review process and the clean-room renderer/differential checks required by the protocol are resolved or marked indeterminate.

Renderer agreement is evidence about implementation ambiguity, not evidence that the clinical fact graph or contract is inherently correct.

## Public audit trail

Where governance permits, the reproducibility release should include:

- completed freeze manifest;
- preregistration hash/reference;
- frozen component hashes/versions;
- dependency manifest;
- sealed-set manifest hash (without restricted case content where necessary);
- post-freeze amendment history;
- final unsealing event metadata;
- scripts reproducing the readiness check and instrument statistics.

The objective is that a reviewer can determine exactly what was frozen, when it was frozen, and whether any measurement-relevant change occurred after the sealed set became visible.


The final freeze record therefore binds the instrument, dependencies, sealed case manifest, blinding controls, and acceptance gate before the sealed set is opened.

Freeze-manifest schema v0.5 additionally pins five pre-opening governance,
analysis, and execution artifacts by SHA-256: the pseudonymous reviewer roster,
the sealed case-assignment manifest, the pilot-derived sample-size
preregistration, the confirmatory analysis preregistration, and the confirmatory
model/prompt configuration. The analysis preregistration directly pins both the
sample-size record and model/prompt configuration. Changing any of these
artifacts after the freeze requires a new manifest and follows the same
post-unsealing amendment rules as an instrument change.


## Verifier abstention gate

Pilot qualification of the tri-state verifier must not preprocess
`INDETERMINATE` outputs into a binary class. The calibration record reports
binary sensitivity/PPV on determinate outputs and separately freezes a maximum
runtime-indeterminate rate, evaluated using either its point estimate or the
upper Wilson 95% confidence bound as preregistered. All-indeterminate verifier
output cannot satisfy instrument qualification.

## Confirmatory inference authorization

Completing the freeze manifest is necessary but not sufficient to start model
inference. The executable authorization layer in
`src/fhirbridge/confirmatory_authorization.py` independently rechecks:

- every protocol gate is passed and the protocol ledger is frozen;
- the tooling manifest is frozen and all qualification flags pass;
- the sealed-set freeze audit passes;
- reviewer roster and exact sealed-case assignment coverage are ready;
- analysis and sample-size preregistrations are ready;
- model/prompt configuration is frozen;
- the pilot-derived verifier acceptance gate is preregistered;
- the actual governance artifact SHA-256 values match those pinned in the
  freeze manifest.

A successful authorization is followed by a pre-inference run plan conforming
to `runs/schema/confirmatory_run_plan.schema.json`. The run plan is frozen
while `sealed_set_opened=false` and `inference_started=false`, binds all
critical artifact hashes, and deterministically records the expected provider
call, derived-repair, deterministic-baseline, and total-arm output counts.

The allowed order is therefore:

**freeze → authorize → hash run plan → open sealed set → execute inference**.

There is no supported path that starts confirmatory inference by bypassing these
checks.
