# Path B: Independent third-source rule census v0.3

**Private, development-only triage. Not proof of normative completeness, reviewer
independence, G1 qualification, or permission to use sealed cases.**

## The issue

Two readers may both report `OBR-3` while both overlook a second
independently applicable condition or code binding on that field. The old
v0.2 third-source checker works at the **locus** level and cannot detect
this issue once reviewer data use versioned v0.3 distinct rules.

`fhirbridge.path_b_v03_source_census.audit_v03_independent_source_census`
takes two **original unchanged v0.3 YAML responses and their independent
byte locks**, plus the exact UTF-8 bytes of a third, separately prepared
private JSON source census. Never convert old v0.2 lock bytes into v0.3.

## Blank private census template

Start from
`qualification/hl7v2/required_element_review/examples/third_source_census_v03_blank.json`.
The template has **zero** rules, all twelve bounded scope areas marked
`UNREVIEWED`, and `census_reviewer_id: TO_BE_ASSIGNED`, which cannot pass
the comparison. It does not include any proprietary Edition 5 source text
or suggested normative rule. It must be completed by an independently
qualified source reviewer under authorized licensed-source custody.

Each source area is retained even if not yet reviewed. Mark it
`SOURCE_PAGES_CHECKED` only after checking its actual official pages,
and record page numbers. The `candidate_requirements` array uses:

```json
{
  "coverage_area": "OBR",
  "source_pages": [101],
  "rule": {
    "candidate_rule_id": "EXAMPLE-ONLY",
    "rule_kind": "CONDITIONAL_PREDICATE",
    "locus": "OBR-3",
    "element_kind": "field",
    "usage": "C",
    "cardinality": "1..1",
    "datatype": "EI",
    "max_length": null,
    "condition": "SYNTHETIC TEST CONDITION — NOT HL7 NORMATIVE CONTENT",
    "value_set_or_binding_ref": null,
    "source_grounding_classification": "SOURCE_FACT",
    "classification_rationale": "Example format only",
    "evidence": ["SYNTHETIC EXAMPLE, not an actual source citation"]
  }
}
```

The example above is **illustrative syntax, not evidence**: do not treat its
numbers, locus, condition, or datatype as verified rules. Real rows must be
derived independently from the authorized Edition 5 Common+NG+FRU guide
and December 2024 errata. Cite pages sparingly without reproducing long
copyrighted text. Each distinct R/C requirement receives its own unique
candidate ID, even at the same physical field.

## Output interpretation

- `rules_not_found_in_either_reader`: third-source *candidate* rules whose
  exact rule-content signature was not reported by either first-round reader.
  These may reflect double omission **or** differences of wording/
  interpretation; both require human source adjudication.
- `same_locus_but_no_matching_rule`: a subset of the above where the same
  physical field appears in an initial response, but the third candidate
  predicate, binding or datatype does not. This is the critical issue that
  v0.2 comparisons miss.
- `matching_candidate_rules_requiring_human_review`: exact candidate rule
  content appears in at least one reader, but the source fact, independence
  and completeness are **not certified**.
- `unreviewed_scope_areas`: source sections still unexamined by the third
  reader. Even all reported sections checked is merely self-reported.
- The original two reviewer response digests and **raw third JSON digest**
  bind this private triage to the exact source submissions. Hashes are not
  signatures or evidence of qualified expertise.

The analyzer preserves any two original reader IDs in their exact v0.3
locks and requires the third reviewer to use a different identifier.
It rejects invalid pages, duplicate rule IDs, duplicated substantive
candidate content, placeholder source grounding and mismatched pinned
publication hashes.

For every output:
`independently_established_requirements_denominator=null`,
`scientific_completeness_certified=false`,
`human_adjudication_performed=false`,
`reviewer_independence_verified_by_software=false`,
`G1_qualified=false`, and `confirmatory_permission=false`.

A qualified human adjudicator must **separately** resolve discrepancies,
audit all apparent agreements and independently assess double omissions
against a complete, source-established denominator. Until then scientific
protocol freeze remains NO-GO.

Do not upload genuine third-source census, private reviewer originals or
licensed official PDF pages into this repository or public CI.
