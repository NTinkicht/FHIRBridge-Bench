# Path B rule-level extraction v0.3 — candidate triage only

**Development only. Not an independently qualified edition 5 denominator,
normative validator or substitute for adjudication.**

## Why a new version

Legacy v0.2
`src/fhirbridge/required_element_extraction.schema.json` identifies
**one response row by one physical HL7 locus**. It can miss a second
distinct conditional requirement that shares the same field or group.
The original v0.2 schema, intake lock, reviewer identity, byte hashes and
legacy comparison remain unchanged for evidentiary reproducibility.

Versioned `lri_rule_level_extraction_v03.schema.json` instead adds:
- `candidate_rule_id`: unique **within a single reader's submission**,
  never proof of rule identity across independent readers.
- `rule_kind`: USAGE, CARDINALITY, DATATYPE, VALUE_SET_BINDING,
  CONDITIONAL_PREDICATE, CROSS_FIELD, ERRATA_EFFECT, or other source constraint.
- `locus`: the actual physical HL7 segment/field/component or group anchor.
  Several separate entries may have exactly the **same** physical locus.
- `related_loci`: optional additional physical loci for cross-field
  conditions; a CROSS_FIELD entry must specify them.
- Separate `condition`, `usage`, `cardinality`, `datatype`, `binding`,
  grounding classification, explanation and source evidence per *rule*.

Use neutral blank
`qualification/hl7v2/required_element_review/examples/rule_level_extraction_v03_blank.yaml`
as an **unfilled template**, not the official HL7 ruleset.
This repository contains no source-backed R/C constraints in that template.

## Locking and reconciling

`create_v03_response_lock(original_yaml_bytes)` hashes the exact v0.3
original bytes using a **different lock schema version** from v0.2.
`verify_v03_response_lock` checks all generated lock fields with exact types
and unmodified source bytes. v0.2 original locks can only be verified with
their original v0.2 validator. Never reformat, rewrite or back-convert an
older locked submission as a new source artifact.

`triage_locked_v03_extractions(raw_a, lock_a, raw_b, lock_b)` compares
independently stored original responses. It **never** aligns on
`candidate_rule_id` or only on `locus`:

1. Mechanical candidate matches require *exact equal content* of physical
   locus, kind, usage, cardinality, datatype, length, condition, binding,
   grounding classification and cross-field loci. Reader IDs and prose
   citations are excluded from that mechanical content key.
2. It **separately flags** changes in source citations / rationale for a
   human source audit even when the claimed normative content matches.
3. One-sided candidates remain visible at rule level even when the other
   reader reported several **other** rules at the identical physical locus.
4. The output records per-locus candidate counts, raw response SHA-256s,
   two reader IDs and all unmatched candidate records for *private* source
   review. Equal content means only *matching self-reported candidates*;
   it never proves the underlying normative clause or completeness.

A reviewer can use a different candidate ID for the same rule. Conversely,
**identical candidate IDs do not match differing rule predicates**.
An apparently exhaustive agreement still cannot detect requirements
omitted by *both* readers. Independent human source-census review remains
required.

## Restrictive source and scientific boundaries

An AI reader such as Mistral can draft v0.3 candidate requirements only
after source-hosting permission is independently confirmed. Preserve original
submission bytes privately; do not upload licensed official source documents
or reviewer responses into public GitHub/CI. Keep the actual reviewer
isolated from previously prepared rule inventories and independent readers'
responses. A full scientific intake additionally requires a credible
human adjudicator, a separate bounded completeness denominator and
appropriate institutional decisions.

The code always returns `independently_established_requirements_denominator=null`,
`human_adjudication_performed=false`,
`scientific_completeness_certified=false`,
`G1_qualified=false`, `confirmatory_permission=false`.
No claim of clinical compatibility, validated structural conformance,
scientific freeze, or sealed experiment is made.

**Compatibility warning:** the existing third-source census utility
`path_b_source_census.py` and legacy blinded ZIP remain v0.2 and should
*not* be applied to these v0.3 original locks. Their evolution must be
explicitly versioned and separately tested.
