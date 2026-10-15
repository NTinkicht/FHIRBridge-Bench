# Independent LRI Edition 5 Required-Element Extraction Protocol

Status: **Draft pre-freeze procedure**

## Purpose

The selected LRI target is a combination of the Edition 5 Common, NG, and FRU
components. A small hand-curated list of fields is not sufficient evidence that
the complete bounded target profile has been understood. Before protocol freeze,
two independent extractors must enumerate every load-bearing group, segment,
field, component, and subcomponent in the bounded ORU^R01 slice.

This process is separate from Renderer A implementation and from the current
project inventory. Its purpose is to expose omissions and interpretation
disagreements before the measurement instrument is frozen.

## Source identity

Both extractors work from the **same cryptographically identified Edition 5
guide PDF AND December 2024 errata-letter PDF**. Each response must record
both full SHA-256 digests; comparisons reject missing, invalid or different
errata digests. The blind response schema is now version 0.2.0. The coordinator
must verify that hashes correspond to the independently supplied source
documents, not merely that two readers copied the same expected strings.

**Selected Path B development source:** the pinned authoritative Edition 5 +
2024DEC publication PDF. The study does not wait for an original XML export
to initiate an independently reviewed **bounded** rule inventory. If the exact
machine-readable Edition 5 bundle is later authenticated, it becomes an
optional *prespecified sensitivity/differential comparator*, whose differences
must be disclosed, not silently relabeled as Path B ground truth. An older
NIST profile, commercial implementation, or locally reconstructed profile
cannot establish full Edition 5 machine-profile conformance.

Target profile candidate:

- `LRI_NG_FRU_Profile_V3`
- `LRI_Common_Component_V3`
- `LRI_NG_Component_R1`
- `LAB_FRU_Component`

## Independence

Reader A and Reader B complete their initial extraction without seeing:

- the other reader's extraction;
- `benchmark/lri_required_element_inventory.yaml`;
- Renderer A output or source as evidence of what the profile requires.

The source standard itself, neutral extraction instructions, and generic
classification definitions are permitted.

The machine-readable response format is:

`qualification/hl7v2/required_element_review/schema/required_element_extraction.schema.json`

A deliberately incomplete template is provided under:

`qualification/hl7v2/required_element_review/examples/extraction_template.yaml`

## What each extractor records

For every in-scope locus, record at minimum:

- canonical locus such as `ORDER_OBSERVATION`, `ORC`, `ORC-3`, or a
  component-level path;
- element level: group, segment, field, component, or subcomponent;
- usage: R, RE, C, O, X, or UNKNOWN when the source cannot be resolved;
- cardinality;
- datatype and maximum length where constrained;
- condition/predicate where applicable;
- value-set or binding reference where applicable;
- source-grounding classification:
  `SOURCE_FACT`, `PROFILE_CONSTANT`, `ENVELOPE`, `DERIVED`,
  `UNPROJECTABLE`, or `UNRESOLVED`;
- exact page/table/profile evidence.

An extraction is not freeze-ready while any included locus remains UNKNOWN or
UNRESOLVED. The extraction readiness function also fails closed on placeholder
extractor/extraction IDs, invalid source SHA-256 syntax, wrong target component
metadata, unfinished cardinality/conditional predicates, and placeholder
evidence or rationale. Schema-valid responses and a full pairwise agreement
rate are **not** evidence that the selected published specification has been
completely enumerated. Independent coverage review of the bounded target
remains mandatory.

Never mark extraction complete merely because the checker returns no metadata
blockers: it checks declared entries, not omissions from the standards PDF.

## Comparison

`src/fhirbridge/lri_required_element_review.py` compares two completed
extractions deterministically.

It checks:

- same source artifact SHA-256;
- same profile;
- different extractor IDs;
- no duplicate loci;
- loci present in only one extraction;
- disagreements in usage, cardinality, datatype, maximum length, condition,
  value-set/binding reference, or source-grounding classification;
- exact agreement rate over the union of loci.

The comparison **does not adjudicate** disagreements. Original extractions remain
the evidence.

## First-round response capture (private coordination)

Before either reviewer's initial answers are disclosed to the other or to
adjudicators, store each **original submitted YAML file** in controlled-access,
write-restricted storage and independently retain its byte-level hash record.
A schema-compliant answer need not be marked scientifically complete to be
captured: unresolved and partially complete first-round answers are evidence
and must not be silently replaced by polished second-round answers.

Use the coordinator-only commands from a private working directory:

```bash
python qualification/hl7v2/required_element_review/lock_responses.py lock \
  reviewer-A.yaml reviewer-A.lock.json
python qualification/hl7v2/required_element_review/lock_responses.py lock \
  reviewer-B.yaml reviewer-B.lock.json
python qualification/hl7v2/required_element_review/lock_responses.py compare \
  reviewer-A.yaml reviewer-A.lock.json \
  reviewer-B.yaml reviewer-B.lock.json comparison.json
```

The lock records original UTF-8 YAML bytes, both pinned source digests,
pseudonymous extractor/extraction identifiers, and initial metadata-readiness
blockers. The CLI uses exclusive creation; rerunning cannot overwrite a lock
or comparison output. Pair comparison verifies both lock records before
considering rule disagreement. If a submission remains incomplete or unresolved,
the raw responses stay locked but full rule comparison stays blocked. It does
not declare G1 validity, reviewer independence, or adjudication.

**Security and methodology limitations:** a SHA-256 record is not a digital
signature or proof that a person actually performed an independent review.
Keep first-round responses and locks in separately controlled, time-recorded,
read-only custody; never commit personal reviewer disclosures or confidential
normative PDF files to this public repository. Preserve the original raw
response and create a *new* separately labeled artifact for adjudication or
any corrections.

## Reconciliation

Every disagreement is either:

1. resolved by reference to the source with the original two readings retained;
2. sent to a third standards expert; or
3. retained as `UNRESOLVED`, which keeps the affected mapping outside the
   frozen confirmatory instrument.

**Path B:** two independent initial extractions, mandatory human adjudication
of differences, a predeclared audit sample of agreements, and an explicit
page-by-page completeness check are required. Agreement alone cannot reveal
rules both readers omitted. Independent sign-off must cover all applicable
required and conditional constraints in the prespecified bounded slice.
An AI first reader may assist, but it is not a human standards expert.

**Path A sensitivity:** a subsequently acquired exact machine-readable profile
is separately qualified, with a documented differential analysis. Machine
profile reconciliation is mandatory for any **Path A original-profile** claim,
not for starting Path B development.

## Freeze condition

The required-element inventory gate may pass only after:

- both independent extractions are complete;
- all R/RE/C/X and other load-bearing conditional elements in the bounded slice
  are represented;
- disagreements are adjudicated or explicitly unresolved;
- the **selected Path B** ruleset has been independently adjudicated for
  source coverage and qualified with positive and expected-locus negative
  controls (original machine-profile reconciliation only for Path A claims);
- no silent requirement is inferred from Renderer A, Renderer B, or model output.
