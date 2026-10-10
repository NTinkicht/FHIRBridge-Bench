# HL7 v2 LRI profile qualification

The confirmatory HL7 v2 structural oracle requires the exact **HL7 v2.5.1 LRI Edition 5 + 2024DEC** IGAMT-exported XML profile bundle for the selected ORU^R01 component.

Do not substitute the pinned historical NIST LRI R2 comparator or a local implementation guide.

Once the exact bundle has been acquired:

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
`benchmark/structural_validity_policy.yaml`. Confirmatory inference remains
blocked until the exact Edition 5 profile has been qualified and its
warning/alert behavior has been reviewed and frozen.
