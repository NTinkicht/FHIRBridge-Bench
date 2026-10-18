# HL7 v2 LRI profile qualification

## Current route: Path B bounded G1 qualification (not yet complete)

The PI approved **development** of an independently extracted, adjudicated,
bounded HL7 v2.5.1 LRI Edition 5 + 2024DEC conformance oracle for the selected
general-laboratory ORU^R01 scope. Subsequent custodian correspondence reports
that Edition 5 was never codified in IGAMT. That private correspondence is
not a redistributable standards artifact; do not quote or identify the sender
in this public repository.

The original machine-readable IGAMT bundle is therefore **not a development
dependency**. Path B must pin the guide and errata hashes, independently
extract and adjudicate all applicable scoped Common + NG + FRU requirements,
declare completeness and unresolved coverage, qualify deterministic positive
and expected-locus negative controls, and establish source-grounded faithful
outputs for all retained LAB families. Unreviewed mandatory/conditional
requirements must not be treated as passing. A G0 syntax check is not G1
bounded qualification, and G1 passing is not full original-profile conformance.

Use the blind reviewer handoff at
`docs/path_b_independent_reviewer_handoff.md` and the independent extraction
protocol at `docs/lri_required_element_extraction_protocol.md`.
The present tooling and prospective estimand still require a separately
reviewed and authorized alternative freeze gate. No sealed data or
confirmatory inference is authorized.

Do not substitute the pinned historical NIST LRI R2 comparator, APHL
newborn-specific requirements, or a local implementation guide as Edition 5
general-laboratory ground truth.

## Optional Path A: original profile sensitivity qualification

The existing CDC/NIST XML-profile intake below is retained **only** if an
authenticated complete Edition 5 + 2024DEC machine-readable bundle is
independently obtained in the future. It is not the Path B validator.

If such an exact bundle becomes available:

```bash
python qualification/hl7v2/inspect_profile.py /absolute/path/to/profile-bundle
```

The command:

- requires the case-sensitive `PROFILE.xml` file expected by the current CDC/NIST wrapper; do not rename an acquired source artifact merely to satisfy this assumption;
- preserves and hashes every safe file in the selected profile subtree, including previously unknown companion artifacts, while excluding only explicit operating-system junk;
- computes per-file and aggregate SHA-256;
- verifies HL7 version 2.5.1 and ORU^R01 / ORU_R01 identity;
- requires exactly one selected ORU^R01 message profile so the validator cannot silently choose among multiple variants;
- writes only provenance metadata to `qualification/hl7v2/results/`.

After provenance review, the same frozen bundle is used with `gov.cdc:lib-hl7v2-nist-validator:1.5.0`. Reference messages and structural-negative controls must both be evaluated before `profile_validation_qualification_passed` can be set true.

The profile XML itself should only be committed when redistribution is explicitly permitted. Otherwise commit hashes, source/acquisition metadata, and qualification reports only.


If HL7/IGAMT provides the resource bundle as a ZIP, inspect it directly without manually extracting it:

```bash
python qualification/hl7v2/inspect_profile_archive.py /absolute/path/to/igamt-export.zip
```

The ZIP inspector is intentionally conservative: it requires exactly one `PROFILE.xml`, preserves every safe file in that profile directory/subtree for the deterministic scientific bundle hash, rejects ambiguous multi-ORU exports, and records the archive SHA-256 in addition to the bundle hash. Path-traversal members are ignored rather than extracted. If an official Edition 5 export uses a different profile filename or contains several selectable ORU profiles, do not rename or edit it; preserve the original package and extend the selector-capable intake path before freeze.


## End-to-end local qualification

After acquiring the exact Edition 5 + 2024DEC profile bundle and completing the
provenance inspection, prepare the pinned validator dependency once:

```bash
git clone https://github.com/CDCgov/lib-hl7v2-nist-validator vendor/lib-hl7v2-nist-validator
git -C vendor/lib-hl7v2-nist-validator checkout eeac90c5f88dca3018992005232acdf3da644d88
```

Then run:

```bash
python qualification/hl7v2/run_local_profile_qualification.py /absolute/path/to/profile-bundle
```

The runner:

- rejects bundles that are not unambiguously HL7 v2.5.1 ORU^R01;
- compiles the pinned Java 17 CDC/NIST validation harness;
- renders a deterministic current Renderer A reference artifact;
- validates that artifact against the exact local profile;
- generates high-confidence structural negative controls for wrong HL7 version,
  wrong message identity, and missing patient context;
- requires every negative control to produce at least one NIST error;
- writes a machine-readable qualification report under
  `qualification/hl7v2/results/local-profile/`.

The authoritative Edition 5 publication now establishes the base ORC/OBR
requiredness, key order fields, and equality constraints. Machine-level negative
controls for those rules remain blocked until the exact Edition 5 profile bundle
shows how the validator encodes/enforces them. A green local qualification must
therefore use the exact pinned bundle, a source-grounded reference message, and
frozen negative controls with expected error locations/classifications rather
than accepting any nonzero error as sufficient evidence.


## Structural-validity policy

The local qualification harness now preserves the entry-level NIST validation
report as well as compact counts for Error, Warning, Alert, and Informational
classifications.

Pre-freeze qualification is deliberately fail-closed:

- any Error blocks structural validity;
- any Warning or Alert remains `POLICY_UNRESOLVED` until an explicit
  Edition-5-specific policy or allowlist is frozen;
- Informational entries are retained as evidence but do not block;
- validator execution/profile-load/report-parsing failures are
  `MEASUREMENT_FAILURE`, never valid;
- a structural negative control passes only when an Error is observed at its
  preregistered expected locus, not merely because some unrelated error exists.

The machine-readable candidate policy is
`benchmark/structural_validity_policy.yaml`. Confirmatory inference remains blocked until the selected qualification
route has independently passed its own G1 coverage/positive-negative-control
and warning/alert policy reviews, the prospectively amended estimand is
approved, and all remaining scientific freeze gates have passed. The optional
exact-profile sensitivity path requires its own separate qualification.
