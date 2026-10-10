# Statistical Analysis Plan — Draft v0.1

Status: **Draft — not yet pre-registered**

## Primary estimand

Primary endpoint: **Valid-but-Unfaithful Rate (VUR)** in FHIR → HL7 v2.

VUR is the proportion of structurally valid outputs containing at least one major semantic-fidelity error.

A major semantic-fidelity error is a pre-registered severity-threshold event belonging to one of:

- fabrication;
- semantic corruption;
- required omission.

### Indeterminate measurement outcomes

The transformation-level semantic result is tri-state: `FAITHFUL`,
`UNFAITHFUL`, or `INDETERMINATE`.

- Contract dimensions declared `INDETERMINATE` before inference are outside the
  confirmatory semantic construct and are not promoted into errors by the
  verifier.
- A runtime `INDETERMINATE` outcome caused by grounding ambiguity, an
  unavailable/failed frozen equivalence provider, or another measurement
  boundary is **never counted as faithful**.
- The runtime indeterminate rate is reported for every arm/model.
- Structurally valid transformations with runtime-indeterminate endpoint status
  are routed to blinded human adjudication under the frozen rubric where
  feasible. If adjudication remains indeterminate, those cases remain visible,
  are excluded from the binary VUR numerator and denominator, and the exact
  denominator loss is reported.
- Best-case/worst-case sensitivity analyses treat unresolved transformation-level
  indeterminates respectively as faithful and unfaithful.
- The pilot will determine and preregister an acceptable maximum runtime
  indeterminate rate before confirmatory inference. Exceeding that gate downgrades
  automated population-level VUR analysis to exploratory rather than silently
  changing the scoring policy.

## Unconditional companion estimand

VUR intentionally conditions on structural validity, so it must not be reported
alone. The protocol also preregisters **Valid-and-Faithful Yield (VFY)**:

> VFY = number of attempted transformations that are structurally valid and
> semantically `FAITHFUL` / number of attempted transformations.

The denominator is **all attempted transformations** in the analysis set, not
only structurally valid outputs. Structurally invalid outputs and runtime
`INDETERMINATE` outputs therefore do not count as faithful successes.

For every arm/model/direction, report the following mutually informative
quantities together:

- structural validity rate = VALID / attempted;
- structural invalidity rate = INVALID / attempted;
- measurement-failure rate = MEASUREMENT_FAILURE / attempted;
- structural-policy-unresolved rate = POLICY_UNRESOLVED / attempted;
- VFY = valid and faithful / attempted;
- valid-and-unfaithful yield = valid and unfaithful / attempted;
- valid-indeterminate yield = valid and runtime-indeterminate / attempted;
- VUR among structurally valid determinate outputs, with its existing
  indeterminate sensitivity bounds.

This companion estimand prevents an intervention from appearing safer merely
because it reduces the number of outputs that enter the VUR denominator.

The reference endpoint implementation consumes the four frozen structural
outcomes directly. `MEASUREMENT_FAILURE` and `POLICY_UNRESOLVED` are never
coerced to either VALID or ordinary INVALID for VUR analysis.

## Instrument-validation gate

The main LLM analysis is confirmatory only if the semantic verifier meets pre-registered acceptance thresholds on the sealed expert-validation set.

The final thresholds will be fixed after pilot calibration. Candidate criteria include lower confidence bounds for:

- sensitivity for major fidelity errors;
- positive predictive value for major fidelity errors;
- transformation-level agreement with adjudicated expert labels.

If the verifier fails the gate, downstream LLM comparisons become exploratory.

## Primary hypothesis

The final numeric margin will be fixed after pilot data and before confirmatory inference.

General form:

> Among structurally valid FHIR → HL7 v2 outputs, VUR exceeds a pre-specified non-trivial threshold.

## Secondary hypotheses

Candidate secondary analyses:

1. syntax-validator repair increases structural validity more than semantic fidelity;
2. FHIR → HL7 v2 exhibits a different semantic-error profile than HL7 v2 → FHIR;
3. claimed provenance differs materially from independently verified provenance in a provenance-constrained arm.

Secondary hypotheses will be finalized before Protocol v1.0 freeze.

## Core comparison arms

Planned confirmatory arms:

- deterministic baseline;
- direct structured LLM generation;
- mapping-aware LLM generation;
- mapping-aware + syntax-validator repair.

A provenance-constrained arm may be included as a secondary experiment.

## Statistical unit

Primary unit of analysis: **transformation instance**.

Repeated transformations derived from the same canonical patient/scenario must be treated as clustered observations.

## Planned analyses

### Descriptive estimates

For every arm/model/direction:

- structural validity with Wilson 95% CI;
- structural invalidity, measurement-failure, and policy-unresolved rates;
- Valid-and-Faithful Yield (VFY) with Wilson 95% CI;
- valid-and-unfaithful yield and valid-indeterminate yield;
- VUR with 95% CI;
- fabrication rate;
- omission rate;
- corruption rate;
- distribution of corruption subtypes;
- declared-loss inventory;
- API/system failure rate.

### Paired comparisons

Where the same source instance is processed by multiple strategies:

- paired absolute risk differences;
- **two-sided exact McNemar tests** using the discordant-pair binomial
  distribution for paired binary outcomes;
- **paired cluster percentile-bootstrap 95% confidence intervals**, resampling
  source patient/scenario clusters and retaining all paired rows within each
  sampled cluster;
- **10,000 bootstrap iterations** for confirmatory analyses;
- the bootstrap random seed must be frozen in the analysis manifest before any
  confirmatory model inference.

The `analysis_cluster_id` is assigned in the sealed case manifest before
confirmatory execution and is propagated unchanged into analysis rows. Cluster
identity must not be reconstructed, merged, or split using model outputs,
verifier outcomes, or expert labels.

The paired analysis set is constructed before looking at strategy outcomes. For
VUR comparisons, a source instance enters the paired binary comparison only when
the corresponding transformations in both compared arms satisfy the frozen
structural-validity policy and have determinate semantic endpoint verdicts.
Counts excluded because one or both arms are structurally invalid,
measurement-failure, policy-unresolved, or semantic-indeterminate are reported
by reason. VFY comparisons use all paired attempted transformations and
therefore do not condition on structural validity.

### Mixed-effects modeling

Candidate confirmatory model:

`major_fidelity_error ~ strategy + direction + message_family + complexity + (1 | patient_or_scenario) + (1 | model)`

Exact model form will be finalized after pilot inspection of design balance and convergence.

### Multiplicity

The primary endpoint has one pre-specified confirmatory hypothesis.

Secondary pairwise strategy comparisons will use the **Holm step-down
family-wise correction** on the predeclared comparison family. A different
hierarchical testing procedure may replace Holm only if it is fully
preregistered before confirmatory inference; it cannot be selected after
examining confirmatory p-values.

### Reproducible statistical implementation

The dependency-light reference implementation is
`src/fhirbridge/analysis_statistics.py` and is covered by deterministic tests.
It implements:

- Wilson 95% intervals for binomial proportions;
- paired absolute risk differences and discordant-pair counts;
- two-sided exact McNemar p-values;
- paired cluster percentile-bootstrap risk-difference intervals;
- Holm-adjusted p-values in the original comparison order.

Paired analysis-set construction is implemented in
`src/fhirbridge/analysis_sets.py`. For VUR it includes a case only when both
arms are structurally `VALID` and semantically determinate, and reports each
excluded case by preregistered reason. For VFY it retains every explicitly
attempted paired transformation; missing arm output is an error and must instead
be represented explicitly as `MEASUREMENT_FAILURE`.

Analysis-set rules, cluster identifiers, comparison families, and bootstrap seed
must be frozen in the run/analysis manifest before confirmatory inference.

### Effect size reporting

Primary reporting emphasizes:

- absolute risk differences;
- risk ratios where interpretable;
- 95% confidence intervals;
- p-values only as supporting evidence.

## Verifier-validation analysis

The semantic verifier will be evaluated against a blinded expert-adjudicated reference standard.

Report:

- effective sensitivity across **all expert-positive cases**, counting verifier
  `INDETERMINATE` outcomes on expert-positive cases as missed automated
  detections;
- effective specificity across all expert-negative cases;
- positive predictive value and negative predictive value for determinate
  verifier calls;
- effective transformation-level accuracy across all validation cases;
- overall runtime-indeterminate rate;
- runtime-indeterminate rates/counts stratified by expert-positive versus
  expert-negative reference status;
- determinate-only sensitivity/specificity as diagnostic selective-classifier
  quantities, never as substitutes for the effective primary validation
  metrics;
- category-level precision/recall where supported;
- Wilson 95% confidence intervals.

Inter-rater reliability before adjudication:

- Cohen's kappa for pairwise assignments where appropriate;
- Gwet's AC1 as a prevalence-robust companion statistic;
- raw agreement.

## Expert-gold sampling

Current planning target:

- development/calibration subset;
- sealed confirmatory subset;
- stratification by direction, message family, strategy, model family, and preliminary verifier status;
- enrichment for expected error cases permitted only if population estimates are reweighted appropriately.

Exact sample size will be determined from pilot error prevalence and desired CI precision.

## Sample-size principle

The study will not choose benchmark size by prestige.

Pilot data will estimate:

- VUR prevalence;
- discordant-pair frequency between strategies;
- verifier sensitivity/PPV;
- within-scenario clustering.

These quantities will drive final power and precision calculations before Protocol v1.0 freeze.

## Exclusions

No post-hoc exclusion of difficult cases is allowed.

Pre-specified exclusions may include:

- corrupted benchmark artifacts;
- infrastructure/API failures unrelated to model output;
- contract facts classified `INDETERMINATE` before the run.

All exclusions must remain visible in the run manifest.

## Missing/system failures

System failures are reported separately and are not silently removed from denominators.

The protocol will specify whether API failure counts as an attempted transformation failure for each analysis.

## Direction asymmetry

FHIR → HL7 v2 and HL7 v2 → FHIR are not assumed to be equivalent tasks.

Any cross-direction comparison must distinguish:

- required preservation;
- permitted loss;
- target-profile constraints;
- native versus v2-shaped FHIR where applicable.

## Pre-registration

Before confirmatory model runs, archive/tag:

- Protocol v1.0;
- frozen contract versions;
- frozen verifier commit;
- model/prompt configurations;
- primary endpoint definition and unconditional VFY companion estimand;
- primary threshold/margin;
- exact statistical tests, comparison-set rules, cluster definition, and bootstrap seed;
- multiplicity procedure;
- sample-size justification.
