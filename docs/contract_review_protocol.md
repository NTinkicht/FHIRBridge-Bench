# Projectability Contract Review Protocol — Draft v0.2

Status: **Draft — required before Contract v1.0 freeze**

## Objective

The projectability contract is a study instrument. It must not become an unmeasured private opinion about how FHIR should map to HL7 v2.

This protocol defines how contract rules are externally reviewed before they are used in confirmatory scoring.

## Scope of review

Reviewers evaluate the defensibility of each contract rule independently of any LLM or deterministic converter output.

For each rule, reviewers classify the source fact into exactly one projectability state:

- `MUST_PRESERVE`
- `MAY_TRANSFORM`
- `MAY_LOSE`
- `MUST_NOT_INFER`
- `INDETERMINATE`

Stage-1 reviewers classify projectability without seeing the study team's proposed operations. In Stage 2, reviewers assess whether the disclosed proposed operations are licensed by the named source and target profiles.

## Reviewer requirements

Minimum target:

- two independent external reviewers for the contract-agreement study;
- reviewers should have substantial practical or standards experience with HL7 v2 and FHIR;
- at least one reviewer should have laboratory-interface experience for the initial LRI/ORU^R01 contract;
- reviewers must not use outputs from the study's LLMs to decide the rule;
- initial reviewers must not have authored the projectability rules or implemented either reference renderer;
- prior project involvement, recent collaboration/co-authorship with the study team, and involvement in authoring the relevant LRI material must be disclosed before assignment;
- a relationship that could reasonably compromise independent initial classification disqualifies the reviewer from the agreement pair or is retained only as a disclosed adjudicator/domain consultant.

A third reviewer/adjudicator may resolve disagreements after the independent classifications are locked.

## Two-stage anti-anchoring procedure

The agreement study uses two strictly ordered stages.

**Stage 1 — blind classification.** Reviewers receive the canonical source fact,
source-profile context, named standards/profile versions, neutral evidence
sources, and review questions. They do not receive the study team's proposed
target locus, projectability class, operations, equivalence rule, failure type,
severity, or renderer behavior. Each original Stage-1 response is retained and
hashed before any proposal is revealed.

**Stage 2 — proposal-aware critique.** Only after Stage 1 is locked may the
reviewer see the study proposal and assess its target locus, operations,
equivalence rule, failure class, and severity. The Stage-2 response records the
SHA-256 of the locked Stage-1 response. Stage-2 comments may inform adjudication
but cannot replace Stage-1 labels in the agreement analysis.

## Materials shown to reviewers

For every Stage-1 rule:

- canonical fact definition;
- source FHIR profile path(s);
- named implementation-guide versions;
- neutral standards/profile evidence citations;
- neutral review questions.

Proposed target loci, projectability labels, allowed operations, equivalence
rules, failure types, and severities are withheld until Stage 2.

Reviewers do not see:

- model performance;
- model outputs;
- verifier output;
- renderer disagreements unless a separate post-classification adjudication phase is being conducted.

## Agreement study

The original blind Stage-1 labels are independently classified before adjudication.

Planning target: approximately 150 rule decisions once the contract is sufficiently broad. If the first frozen laboratory contract contains fewer unique fact rules, review all rules rather than sampling.

Report:

- raw agreement;
- Cohen's kappa for two reviewers where appropriate;
- Gwet's AC1 as a prevalence-robust companion;
- confusion matrix across projectability classes;
- disagreement reasons.

Do not calculate agreement from Stage-2 proposal critiques or after adjudication and present it as inter-rater reliability.

## Adjudication

For disagreement:

1. preserve both original reviewer labels;
2. record the disputed evidence/rationale;
3. adjudicator selects a final state only when defensible from standards evidence and the scoped clinical use case;
4. if stable agreement cannot be established, classify the rule as `INDETERMINATE` for the primary endpoint.

Ambiguity is a benchmark finding, not a defect that must be hidden.

## Evidence hierarchy

Rule evidence should be recorded in the following order where applicable:

1. named HL7 implementation guide/profile constraints;
2. normative/base-standard field semantics;
3. published terminology or unit mapping sources;
4. externally reviewed study assumption required to make reverse projectability finite;
5. local benchmark-profile assumption, explicitly labeled as such.

A deterministic converter's output is never sufficient evidence by itself.

## ConceptMap contamination control

If a mapping artifact is supplied to a model in the mapping-aware arm, the same artifact must not become the sole reason a verifier accepts the output.

For each rule, record whether evaluation evidence is:

- `PROMPT_EXPOSED`
- `PROMPT_HELD_OUT`
- `INDEPENDENT_INVARIANT`
- `EXPERT_DECISION`

Primary analyses should report performance on prompt-exposed and prompt-held-out rules separately when sample size permits.

## Clean-room implementation relationship

Renderer A and Renderer B implement the frozen contract but do not validate the contract itself.

Their agreement demonstrates implementation reproducibility, not truth.

Renderer disagreement is used to locate:

- underspecified rules;
- incompatible assumptions;
- coding defects;
- target-profile ambiguity.

Any rule changed because of renderer disagreement must be re-reviewed before the contract is frozen.

## Contract sensitivity analysis

Before final publication, define at least one plausible alternative interpretation for a subset of genuinely ambiguous rules when external experts identify such alternatives.

Recompute the primary endpoint under that alternative contract subset.

The aim is not to manufacture robustness but to show whether the main conclusion depends materially on subjective reverse-mapping choices.

## Freeze requirements

Contract v1.0 may be frozen only when:

- every primary-endpoint rule has a standards/expert evidence record;
- external independent review is complete;
- agreement statistics are archived;
- unresolved disputes are marked `INDETERMINATE`;
- renderer A/B implementations are not being used to rewrite rules post hoc;
- contract file and review decision file are versioned and tagged.

## Post-freeze amendments

Any change to a primary-endpoint rule after model confirmatory runs begin requires:

- a protocol amendment;
- explicit old/new rule comparison;
- reason for change;
- sensitivity analysis using the original frozen contract where technically possible.

No rule may be weakened because a model performs poorly on it.