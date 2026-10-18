# Expert Output Review Packet — Semantic-Verifier Criterion Validation

Status: **Draft reviewer packet — use only after the verifier/contract freeze gates are satisfied**

## Purpose

This review validates the **FHIRBridge-Bench semantic verifier as a measurement instrument**. Reviewers are not being asked to rank models, evaluate prompt quality, or select a preferred converter.

The primary question for each transformation is:

> Does the target contain at least one **major semantic-fidelity error** in a fact eligible for scoring under the frozen projectability contract?

The expert reference standard is produced from blinded, independent primary reviews followed by separate adjudication of disagreements.

## What reviewers receive

For each case, reviewers receive only:

- a case identifier;
- the source interoperability artifact;
- the target interoperability artifact;
- the relevant canonical clinical facts;
- the frozen human-readable projectability rule(s);
- the annotation form and severity rubric.

Artifact hashes are recorded so both reviewers score the same immutable source/target pair.

## What reviewers must NOT receive during initial labeling

Do not reveal:

- model identity or provider;
- generation/prompt strategy;
- whether an output came from an LLM or deterministic converter;
- the semantic verifier's decision;
- the verifier's grounding/evidence trace;
- model-emitted provenance or source citations;
- another reviewer's labels;
- deterministic reference output used as an anchor.

If a deterministic or external reference is consulted during later adjudication, that exposure must be recorded as post-label information and must not be presented as ground truth.

## Error taxonomy

### `FABRICATION`
A target clinical assertion has no permissible grounding in the source and is not licensed by a frozen derivation rule.

For this study, the word **hallucination** is reserved for unsupported fabrication rather than used for every type of transformation error.

### `CORRUPTION`
A target assertion is grounded in a legitimate source fact but its clinical meaning is altered.

Diagnostic subtypes may include:

- value;
- terminology/code;
- unit;
- identifier;
- temporal information;
- relationship/reference;
- status;
- other.

### `OMISSION`
A source fact classified by the frozen contract as required for preservation is absent from the target.

### `MISATTRIBUTION`
Otherwise plausible content is attached to the wrong patient, order, result, specimen, report, encounter, or other clinical context.

### `NONE`
No semantic-fidelity error is identified for the annotated fact under the frozen contract.

### `INDETERMINATE`
The frozen contract or available evidence is insufficient to support a defensible classification. Do not force a binary label in an ambiguous case.

Licensed normalization, permitted derivation, and explicitly permitted representational loss are **not errors** when the frozen contract conditions are satisfied.

## Error precedence

When one root defect produces several apparent downstream consequences, avoid mechanically counting each consequence as an independent error.

Use the study precedence policy:

**MISATTRIBUTION → CORRUPTION → OMISSION → FABRICATION**

Example: a valid laboratory value attached to the wrong patient is primarily a **MISATTRIBUTION**, not simultaneously counted as an omission for patient A plus fabrication for patient B plus identifier corruption.

Where two independent defects genuinely coexist, record both at fact level.

## Severity axis

Severity is separate from error type.

### `S0 — benign/cosmetic`
No change to clinical meaning or intended interoperability semantics.

### `S1 — interoperability-relevant`
Could affect parsing, routing, or machine interpretation but is not expected to alter a clinical fact.

### `S2 — clinically meaningful`
Changes, removes, or invents information that could alter interpretation or downstream decision-making.

### `S3 — potentially safety-critical`
High-impact defects such as wrong-patient/wrong-result attachment or materially incorrect clinical values/units/status when the error could plausibly lead to unsafe downstream use.

The S2/S3 boundary must be calibrated in the development set before the sealed test begins. Do not revise severity anchors after sealed cases are opened.

## Transformation-level verdict

Choose exactly one:

- `YES` — at least one **major** semantic-fidelity error is present in a scored fact;
- `NO` — no major semantic-fidelity error is present in scored facts;
- `INDETERMINATE` — the frozen contract/evidence is insufficient for a defensible transformation-level verdict.

The exact definition of **major** is frozen before sealed evaluation. The reviewer form must display that definition explicitly.

## Fact-level annotation

For every suspected error, record:

- annotation ID;
- canonical fact ID when applicable;
- source evidence location(s);
- target evidence location(s);
- applicable contract rule ID(s);
- error class;
- corruption subtype when applicable;
- severity;
- confidence;
- concise rationale/comment.

A fabrication may have no source fact ID because unsupported content can originate only in the target; record the target evidence and the failed grounding rationale.

## Reviewer confidence

Use:

- `HIGH` — the source, target, and frozen rule provide a clear answer;
- `MODERATE` — some interpretive judgment is required but one decision is better supported;
- `LOW` — substantial ambiguity remains.

Low confidence is not a reason to guess. Use `INDETERMINATE` when the rule/evidence genuinely cannot resolve the case.

## Independent review procedure

1. Reviewer A and Reviewer B label each assigned case independently.
2. Original labels are locked and hashed before reviewer disagreement is disclosed.
3. Pre-adjudication reliability is computed from the original labels only.
4. Disagreements are sent to a third adjudicator.
5. The adjudicator sees both primary labels and may consult additional standards material if needed.
6. The adjudicated label is stored in a **separate record** referencing the hashes of both primary annotations.
7. Raw labels are never overwritten.

Do not report agreement statistics on adjudicated labels as inter-rater reliability.

## Development versus sealed cases

### Development/calibration set
May be used to:

- clarify annotation wording;
- calibrate S2/S3 severity anchors;
- identify usability problems in the annotation interface;
- expose categories the frozen protocol cannot reliably operationalize before final freeze.

### Sealed confirmatory set
Must not be used to:

- tune the verifier;
- change projectability rules;
- change error precedence;
- change the major-error threshold;
- modify acceptance thresholds.

If a post-unsealing instrument change is unavoidable, the affected analysis becomes exploratory unless a fresh untouched sealed set is available.

## Planned agreement reporting

Report before adjudication:

- raw transformation-level agreement;
- Cohen's kappa where appropriate;
- Gwet's AC1 as a prevalence-robust companion;
- category-level agreement where support permits;
- disagreement patterns and reasons.

## Planned verifier criterion-validation reporting

Against the sealed adjudicated reference standard, report:

- sensitivity for major semantic-fidelity error;
- specificity;
- positive predictive value;
- negative predictive value;
- accuracy;
- 95% confidence intervals;
- false-positive and false-negative audit;
- per-class precision/recall only when the sample supports meaningful estimates.

The acceptance gate is defined after pilot calibration and preregistered **before** the sealed set is opened. The software intentionally contains no default pass threshold.

If the verifier fails the preregistered gate, subsequent model-comparison results cannot be presented as confirmatory semantic-fidelity estimates.

## Reviewer attestation

For every submitted initial annotation, confirm:

- model identity was hidden;
- generation strategy was hidden;
- verifier output was hidden;
- claimed model provenance was hidden;
- the other primary reviewer's label was hidden.

Reviewer ID: ____________________

Relevant expertise: ____________________

Date: ____________________

Signature/confirmation: ____________________
