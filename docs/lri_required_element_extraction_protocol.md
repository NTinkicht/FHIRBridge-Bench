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

Both extractors work from the **same cryptographically identified artifact**.

The first extraction may use the authoritative Edition 5 + 2024DEC publication
PDF. When the exact machine-readable Edition 5 profile bundle becomes available,
the extraction must be repeated or reconciled against that exact bundle. A
historical NIST profile, Labcorp/Quest profile, or locally reconstructed profile
cannot satisfy this requirement.

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

## Reconciliation

Every disagreement is either:

1. resolved by reference to the source with the original two readings retained;
2. sent to a third standards expert; or
3. retained as `UNRESOLVED`, which keeps the affected mapping outside the
   frozen confirmatory instrument.

Machine-bundle reconciliation is mandatory even if the two PDF extractions
agree perfectly.

## Freeze condition

The required-element inventory gate may pass only after:

- both independent extractions are complete;
- all R/RE/C/X and other load-bearing conditional elements in the bounded slice
  are represented;
- disagreements are adjudicated or explicitly unresolved;
- the exact Edition 5 machine profile has been reconciled;
- no silent requirement is inferred from Renderer A, Renderer B, or model output.
