# Mistral Reader A — blind preliminary HL7 Edition 5 extraction

**Role: AI-assisted first-round reader, not a qualified human standards
reviewer.** This document is a neutral handoff. It contains no substantive
Edition 5 R/C rules and must not be supplied together with project renderer
code, previously drafted rule inventories, other reader responses, verifier
predictions or benchmark answers.

## Authorization BEFORE external inference

The coordinator must first confirm the official Edition 5 publication and
December 2024 errata may legally and organizationally be uploaded to the
selected Mistral environment. Do **not** upload licensed source PDFs to a
hosted service without this determination. If unresolved, stop at the
neutral prompt and use no substituted standards or fabricated extraction.

Inputs to the isolated Mistral Reader A environment (only):
- The exact authorized pinned Edition 5 publication and 2024DEC errata.
- The neutral extraction template
  `qualification/hl7v2/required_element_review/examples/extraction_template.yaml`.
- This instruction, and optionally its schema
  `src/fhirbridge/required_element_extraction.schema.json`.
- The bounded target: HL7 v2.5.1 ORU^R01, Edition 5 Common+NG+FRU general
  laboratory components, including MSH, PID, ORC, OBR, OBX, SPM, NTE if
  present, group/cardinality, cross-field predicates, datatype and value
  set bindings, and December 2024 errata effects.

Never expose to Reader A the current project required-element inventory,
renderer code or output, independent human Reader B's work, draft ground
truth, LLM-generated transformed messages or verifier classifications.

## Exact prompt for isolated Mistral

> You are **Mistral AI Reader A**, an AI-assisted preliminary extractor, not
> a human reviewer or final authority on HL7 standards.
>
> From the supplied authorized Edition 5 and December 2024 errata documents
> alone, extract every applicable normative required (R) and conditional (C)
> constraint in the stated bounded general-lab ORU^R01 scope. Review each
> source segment/group and its relevant cross-field, repetition, datatype,
> vocabulary, length, condition and component interactions. Include source
> page/table citations and whether errata alters or qualifies each claim.
> Do not infer an unspecified requirement from examples, an external
> converter, a previous output or general HL7 knowledge.
>
> Produce a YAML document matching the **provided extraction template/schema
> v0.2.0**. Keep its pinned source hashes and edition/component identity.
> Use a unique `extraction_id` for this original run and exactly:
> `extractor.extractor_id: MISTRAL-READER-A` and
> `extractor.role: AI_preliminary_extractor`.
> Include the literal phrase `AI-assisted`, plus exact, nonfloating
> `model_id=<mistral-specific-model>` and
> `model_version=<exact-provider-revision>` values in `notes`
> (no `latest`/unknown aliases), and the actual model/context provenance
> in `extractor.prior_project_involvement`. These are **self-reported**
> identifiers, not independently verified via a provider API.
> Declare conflicts, prior context and any accidental exposure accurately.
> Do **not** represent yourself as a human, claim independent human
> adjudication, or claim scientific standards completeness.
>
> For each claim, record the precise physical HL7 locus, usage,
> cardinality, datatype, permitted source-grounding classification,
> exact condition for C, any value-set binding, and short page-cited
> source-grounded paraphrases. Do not reproduce long copyrighted passages.
> Mark unsupported, ambiguous or not-yet-reviewed positions as UNKNOWN
> or UNRESOLVED with explanation, not as optional or conformant.
>
> **Important schema limitation:** v0.2.0 comparison assumes one entry per
> physical `locus`. When the official source attaches **more than one
> distinct applicable constraint to the same locus**, do **not** silently
> combine them, invent different physical loci, or mark the extraction as
> complete. Identify all additional distinct predicates/requirements in
> `notes`, with precise source-page pointers, clearly state that separate
> rule identity support is needed, and set `extraction_complete: false`.
> Such unresolved multi-rule cases must be imported into a versioned
> expanded requirement format and reviewed independently before coverage
> certification.
>
> If any bounded section has not been reviewed or any R/C claim remains
> unresolved, set `extraction_complete: false`. Do not fabricate pages,
> clauses, readiness or validator outcomes. Return only the YAML response,
> retaining all original uncertainty.

## Custody handoff (private/local)

1. Capture the **unchanged first response bytes** outside the public
   repository. Do not reformat or correct them before hashing, even when
   syntactically incomplete.
2. After obtaining actual authorization, a coordinator with a local
   Python environment can produce the byte-locked response JSON using:

```sh
python qualification/hl7v2/required_element_review/intake_mistral_reader_a.py \
  /private/reviews/mistral-reader-a-original.yaml \
  /private/reviews/mistral-reader-a-original.lock.json \
  --source-use-authorized
```

The tool refuses repository-local input/output paths, rejects missing
AI authorship fields, checks the pinned publication identity and first-round
format, creates the original lock **exclusively with private file permissions**
and returns no copyrighted/source content on stdout. The authorization flag
is only a **coordinator declaration**, not independently verified permission.

If the input is incomplete/UNKNOWN, its original response can still be
locked for later transparent adjudication. A syntactically complete-looking
response does not establish standards completeness or qualified human
review. The lock is a digest, not a signature.

**Accidental exposure must be reported truthfully.** If the Mistral response
declares a breach of one of the three isolation flags, the coordinator
still preserves the unmodified original with a distinct
`AI_FIRST_ROUND_EXPOSURE_QUARANTINED` SHA-256 receipt. This is **not**
a normal `verify_response_lock` artifact, never qualifies as an independent
source extraction, and makes the private CLI return **exit code 2** after
securely recording the quarantine receipt. Do not edit the exposed original
to set its disclosure flags back to false. If model/version provenance is
missing, normal intake fails and the original must still be retained in
private custody rather than rewritten to claim an unknown revision.

## Scientific guardrails

- Independent human Reader B must remain blind to the Mistral response.
- A genuinely separate qualified human adjudicator reviews disputes,
  observed agreements and missing-from-both possibilities against official
  source pages.
- The existing source-census triage records candidates absent from both
  original lists, not a certified denominator.
- Never upload any licensed PDFs, original reviewer responses, source
  citations or private custody artifacts to this public repository.
- `independent_human_extraction_received=false`,
  `requirements_denominator_qualified=false`,
  `G1_qualified=false` and `confirmatory_permission=false` throughout
  this software-only intake.
