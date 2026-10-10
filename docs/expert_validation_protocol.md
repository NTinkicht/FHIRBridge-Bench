# Expert Validation Protocol — Draft v0.1

Status: **Draft — numbers to be recalculated after pilot**

## Purpose

The expert study validates the **semantic verifier as a measurement instrument**. Experts are not intended to manually grade the full benchmark.

The verifier must be frozen before the sealed confirmatory expert set is opened.

## Reference-standard design

The expert reference standard is based on blinded review of naturally occurring transformation outputs plus a separately labeled seeded-fault suite.

The primary criterion is whether a transformation contains at least one **major semantic-fidelity error** under the frozen projectability contract.

Error classes:

- FABRICATION — unsupported target clinical content;
- CORRUPTION — grounded content with altered meaning;
- OMISSION — required source fact absent from the target;
- MISATTRIBUTION — otherwise plausible content attached to the wrong patient/order/result/context;
- licensed normalization/derivation/loss — not errors when permitted by the frozen contract;
- INDETERMINATE — excluded from the confirmatory primary endpoint.

Severity is rated separately from error type.

## Reviewer composition

Each case is independently reviewed by two primary reviewers.

Desired expertise across each reviewer pair:

1. **HL7 v2/FHIR interoperability expertise** — production interface implementation, standards profiling, or equivalent practical experience;
2. **clinical informatics/domain expertise** — ability to judge whether laboratory-result changes alter clinical meaning.

A third senior adjudicator reviews disagreements after pre-adjudication labels are locked.

Where staffing permits, use a pool of at least four reviewers so that results are not dominated by one pair.

Before any sealed case is opened, the pseudonymous reviewer roster must be
locked using `expert_validation/schema/reviewer_roster.schema.json`. The
roster records role assignments, expertise, conflicts, prior project
involvement, contract-review overlap, renderer-implementation overlap, and the
access profile used to enforce blinding. The final freeze manifest pins the
roster artifact by SHA-256.

## Blinding

Primary reviewers receive:

- source artifact;
- target artifact;
- canonical facts relevant to the case;
- frozen human-readable projectability rule(s);
- annotation instructions.

Primary reviewers do **not** receive:

- model identity;
- model/provider name;
- prompt strategy;
- deterministic-converter identity;
- verifier verdict;
- model-emitted provenance/grounding claims;
- another reviewer's label.

Deterministic reference outputs may be shown only during post-label adjudication if needed, and any change caused by that information must be recorded.

Primary reviewers must have a pre-opening access profile that denies model
identity, generation strategy, verifier verdict, model-claimed provenance, and
the other primary reviewer's labels. An adjudicator must be a different
pseudonymous member ID from both primary reviewers.

## Development and sealed sets

Planning target before pilot recalculation:

- **Development/calibration:** approximately 125 transformations;
- **Sealed confirmatory test:** approximately 375 transformations;
- **Total:** approximately 500 transformations.

These are planning values, not a prestige target. Final sizes will be recalculated from pilot estimates of:

- major-error prevalence;
- desired confidence-interval width for verifier sensitivity and PPV;
- reviewer disagreement rate;
- distribution of error classes.

The development set may be used to refine annotation instructions, severity anchors, and non-semantic UI issues.

The sealed set must not be used to tune verifier rules, contract rules, thresholds, or precedence logic.

## Sampling

The expert set should be stratified across:

- FHIR → HL7 v2 and HL7 v2 → FHIR;
- core strategy arms;
- model families;
- laboratory scenario families;
- structurally valid and invalid outputs;
- anticipated error-positive and error-negative cases;
- implementation-variant profiles.

If the sample is deliberately enriched for verifier-positive cases to obtain enough errors for sensitivity estimation, population prevalence estimates must use appropriate sampling weights and the enrichment procedure must be documented.

## Annotation unit

Primary transformation-level question:

> Does this transformation contain at least one major semantic-fidelity error in a fact eligible for the primary endpoint?

Element/fact-level annotations record:

- canonical fact identifier;
- source evidence;
- target evidence;
- error class;
- corruption subtype when applicable;
- severity;
- confidence;
- comments for ambiguity.

## Severity rubric

Draft severity axis:

- **S0 — benign/cosmetic:** no change to clinical meaning or interoperability intent;
- **S1 — interoperability-relevant:** can affect parsing, routing, or interpretation but not expected to change a clinical fact;
- **S2 — clinically meaningful:** changes or removes information that could alter interpretation or downstream decision-making;
- **S3 — potentially safety-critical:** wrong-patient/wrong-result attachment, materially incorrect result value/unit/status, or comparable high-impact error.

The exact S2/S3 anchors must be calibrated with experts before sealed evaluation.

The primary endpoint's definition of **major** must be frozen before the sealed set is opened.

## Agreement analysis

Report agreement **before adjudication**:

- raw transformation-level agreement;
- Cohen's kappa for two-rater binary/nominal labels where applicable;
- Gwet's AC1 as a prevalence-robust companion;
- category-level agreement where cell counts permit.

Do not report adjudicated agreement as inter-rater reliability.

## Verifier qualification

Against the sealed adjudicated expert standard, report:

- sensitivity for major semantic-fidelity error;
- specificity;
- positive predictive value;
- negative predictive value;
- transformation-level accuracy;
- per-class precision/recall where adequately supported;
- 95% confidence intervals;
- false-positive and false-negative case audit.

Candidate acceptance thresholds will be chosen after pilot calibration and pre-registered before the sealed set is opened.

If the verifier fails the pre-registered gate, the main model-comparison results cannot be reported as confirmatory semantic-fidelity estimates.

## Freeze procedure

Before sealed evaluation:

1. tag the projectability contract version;
2. tag the canonical schema version;
3. tag the verifier/lifter commit;
4. publish the annotation rubric version;
5. record a hash/identifier of the sealed-case manifest;
6. pre-register the acceptance thresholds and statistical analyses.

Any post-unsealing change requires either:

- a fresh untouched sealed set; or
- explicit treatment as exploratory instrument redevelopment.

## Seeded-fault suite

Seeded faults test the verifier's known response characteristics, but they do not replace natural model errors.

Fault authors should be separated from verifier-rule authors where feasible.

Fault families should include at minimum:

- unsupported added result/fact;
- dropped required fact;
- wrong numeric value;
- wrong but syntactically valid unit;
- wrong terminology code;
- patient/order/result misattribution;
- timestamp/context corruption;
- plausible but false provenance claim.

Report detection recall by fault family.

## Reviewer independence

External reviewers used to evaluate **contract rules** should be distinct from, or at minimum analytically separated from, the reviewers used to judge model outputs.

Contract review asks whether a rule is defensible.

Output adjudication asks whether a transformation complies with the already frozen rule.

These are different validity questions and should not be conflated.

## Auditability

The public release should include, where governance permits:

- annotation rubric;
- de-identified/synthetic expert cases;
- pre-adjudication labels;
- adjudicated labels;
- disagreement categories;
- verifier decisions for those cases;
- scripts reproducing reliability and instrument-validity statistics.

No restricted patient-level data or derived patient-level outputs are released.