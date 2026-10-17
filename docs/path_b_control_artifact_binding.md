# Exact-byte binding for unrun Path B synthetic controls

The Path B rule evidence register (#30) stores control IDs and planned expected loci; the surgical-diff helper (#31) proves that two synthetic HL7 messages differ at precisely one existing field. **Neither alone proves that the bytes cited by a control manifest are the same bytes actually tested.**

This development utility closes only that construction gap. It accepts an explicit JSON manifest, the associated **unrun** rule record, and two local message files. It verifies the control IDs, required expected field, exact file SHA-256 digests, distinct control files and a one-field surgical mutation. The manifest must have these exact keys:

- `schema_version` = `0.1.0`, `status` = `PREFREEZE_CONSTRUCTION_ONLY`
- `rule_id`, `expected_locus`, `positive_control_id`, `negative_control_id`
- `positive_artifact_sha256`, `negative_artifact_sha256`

The supplied rule record must contain matching `rule_id` / `locus`; both control entries must match the corresponding IDs and expected locus, and must remain `result: UNRUN`, `observed_locus: null`, `evidence_sha256: null`. **A claimed validator pass is explicitly rejected**, not accepted as further evidence. Both artifacts must be local UTF-8 bytes with exact matching hashes. The field-diff helper enforces unchanged HL7 segment order and field structure.

Example (using **synthetic**, authorized, local files only):

```sh
python qualification/hl7v2/bind_synthetic_control_artifacts.py \
  --manifest manifest.json --rule-record rule.json \
  --positive synthetic-positive.hl7 --negative synthetic-negative.hl7
```

Successful output contains identifiers and digests only, plus **constant** `status=PREFREEZE_ARTIFACT_BYTES_BOUND_ONLY`, `G1_qualified=false`, `validator_expected_locus_failure_confirmed=false`, `confirmatory_permission=false`. It does not echo full HL7 message text.

**Do not commit private patient records, raw expert submissions or clinical validation reports.** Passing this checker does not establish independent custody, source requirements validity, baseline conformance, validator rejection at the intended locus, complete coverage, G1 qualification, or confirmatory authorization. Those remain independent scientific and governance gates.
