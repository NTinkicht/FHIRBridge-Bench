# Statistical Analysis Plan — Draft v0.1

Status: **Draft — not yet pre-registered**

## Primary estimand

Primary endpoint: **Valid-but-Unfaithful Rate (VUR)** in FHIR → HL7 v2.

VUR is the proportion of structurally valid outputs containing at least one major semantic-fidelity error.

A major semantic-fidelity error is a pre-registered severity-threshold event belonging to one of:

- fabrication;
- semantic corruption;
- required omission.

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

- structural validity with 95% CI;
- VUR with 95% CI;
- fabrication rate;
- omission rate;
- corruption rate;
- distribution of corruption subtypes;
- declared-loss inventory;
- API/system failure rate.

### Paired comparisons

Where the same source instance is processed by multiple strategies:

- paired risk differences;
- exact or asymptotic McNemar tests for paired binary outcomes;
- paired bootstrap confidence intervals clustered by source scenario/patient.

### Mixed-effects modeling

Candidate confirmatory model:

`major_fidelity_error ~ strategy + direction + message_family + complexity + (1 | patient_or_scenario) + (1 | model)`

Exact model form will be finalized after pilot inspection of design balance and convergence.

### Multiplicity

The primary endpoint has one pre-specified confirmatory hypothesis.

Secondary pairwise strategy comparisons will use a family-wise correction such as Holm unless a hierarchical testing procedure is pre-registered instead.

### Effect size reporting

Primary reporting emphasizes:

- absolute risk differences;
- risk ratios where interpretable;
- 95% confidence intervals;
- p-values only as supporting evidence.

## Verifier-validation analysis

The semantic verifier will be evaluated against a blinded expert-adjudicated reference standard.

Report:

- sensitivity;
- specificity;
- positive predictive value;
- negative predictive value;
- transformation-level accuracy;
- category-level precision/recall where supported;
- 95% confidence intervals.

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
- primary endpoint definition;
- primary threshold/margin;
- exact statistical tests;
- multiplicity procedure;
- sample-size justification.
