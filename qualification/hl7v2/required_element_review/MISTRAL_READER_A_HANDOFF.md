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
  `qualification/hl7v2/required_element_review/examples/rule_level_extraction_v03_blank.yaml`.
- This instruction, and optionally its schema
  `src/fhirbridge/lri_rule_level_extraction_v03.schema.json`.
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
> v0.3.0**. Keep its pinned source hashes and edition/component identity.
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
> For **each distinct normative claim** use an independent
> `candidate_rule_id` (unique within your submission), `rule_kind`,
> the **real physical** HL7 `locus`, usage, cardinality, datatype,
> binding, exact condition for C, any `related_loci` for cross-field
> constraints, source-grounding classification and brief page-cited
> paraphrase. Two or more distinct constraints **may repeat the same
> physical locus**; do not merge them or invent fake physical suffixes.
> A DATATYPE rule must name a datatype and a VALUE_SET_BINDING rule
> must name a binding. Do not create a rule with a missing conditional
> predicate merely to increase coverage.
>
> Your `candidate_rule_id` is **not** a standards identifier and another
> reader may independently use a different ID. Do not treat equal reader
> IDs or the same physical field as confirmation of rule equivalence.
> Report unsupported or unresolved source claims transparently. Do not
> reproduce long copyrighted passages or invent clauses, page numbers
> or accepted validator results.
>
> v0.3 is a **candidate-only** extraction format. Even apparent complete
> extraction or exact cross-reader agreement cannot prove the independent
> source denominator. Only qualified human standards review can do so.
>
> If any bounded section has not been reviewed or any R/C claim remains
> unresolved, set `extraction_complete: false`. Do not fabricate pages,
> clauses, readiness or validator outcomes. Return only the YAML response,
> retaining all original uncertainty.

**Versioning:** This handoff now targets v0.3 rule-level extraction.
Historical v0.2 submission formats and private original locks are preserved
and remain verifiable only through the legacy v0.2 intake. Do **not**
rewrite or migrate any original first response into v0.3; a v0.3 Mistral
run is a new and separately hashed original.

## Custody handoff (private/local)

1. Capture the **unchanged first response bytes** outside the public
   repository. Do not reformat or correct them before hashing, even when
   syntactically incomplete.
2. After obtaining actual authorization, a coordinator with a local
   Python environment can produce the byte-locked response JSON using:

```sh
python qualification/hl7v2/required_element_review/intake_mistral_reader_a_v03.py \
  /private/reviews/mistral-reader-a-v03-original.yaml \
  /private/reviews/mistral-reader-a-v03-original.lock.json \
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
`AI_RULE_LEVEL_V03_EXPOSURE_QUARANTINED` SHA-256 receipt. This is **not**
a normal `verify_v03_response_lock` artifact, never qualifies as an independent
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
- The existing v0.2 source-census triage must not be applied directly to
  v0.3 submissions; build a separately versioned rule-level census. Neither
  method certifies a complete source denominator.
- Never upload any licensed PDFs, original reviewer responses, source
  citations or private custody artifacts to this public repository.
- `independent_human_extraction_received=false`,
  `requirements_denominator_qualified=false`,
  `G1_qualified=false` and `confirmatory_permission=false` throughout
  this software-only intake.
