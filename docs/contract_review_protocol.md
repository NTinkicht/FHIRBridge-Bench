# Projectability Contract Review Protocol — Draft v0.1

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

For `MAY_TRANSFORM`, reviewers also assess whether each listed transformation operation is licensed by the named source and target profiles.

## Reviewer requirements

Minimum target:

- two independent external reviewers for the contract-agreement study;
- reviewers should have substantial practical or standards experience with HL7 v2 and FHIR;
- at least one reviewer should have laboratory-interface experience for the initial LRI/ORU^R01 contract;
- reviewers must not use outputs from the study's LLMs to decide the rule.

A third reviewer/adjudicator may resolve disagreements after the independent classifications are locked.

## Materials shown to reviewers

For every rule:

- canonical fact definition;
- source FHIR profile path(s);
- proposed target HL7 v2 field/segment path(s), if any;
- named implementation-guide versions;
- proposed projectability class;
- proposed allowed operations;
- rationale and evidence citations.

Reviewers do not see:

- model performance;
- model outputs;
- verifier output;
- renderer disagreements unless a separate post-classification adjudication phase is being conducted.

## Agreement study

A stratified sample of contract rules is independently classified before adjudication.

Planning target: approximately 150 rule decisions once the contract is sufficiently broad. If the first frozen laboratory contract contains fewer unique fact rules, review all rules rather than sampling.

Report:

- raw agreement;
- Cohen's kappa for two reviewers where appropriate;
- Gwet's AC1 as a prevalence-robust companion;
- confusion matrix across projectability classes;
- disagreement reasons.

Do not calculate agreement after adjudication and present it as inter-rater reliability.

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