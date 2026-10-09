# HL7 v2 LRI profile qualification

The confirmatory HL7 v2 structural oracle requires the exact **HL7 v2.5.1 LRI Edition 5 + 2024DEC** IGAMT-exported XML profile bundle for the selected ORU^R01 component.

Do not substitute the pinned historical NIST LRI R2 comparator or a local implementation guide.

Once the exact bundle has been acquired:

```bash
python qualification/hl7v2/inspect_profile.py /absolute/path/to/profile-bundle
```

The command:

- requires the case-sensitive `PROFILE.xml` file expected by the CDC/NIST wrapper;
- includes known IGAMT companion files when present;
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

The ZIP inspector is intentionally conservative: it requires exactly one `PROFILE.xml`, copies only known scientific companion files from the same archive directory into a temporary workspace, rejects ambiguous multi-ORU exports, and records the archive SHA-256 in addition to the deterministic bundle hash. Unknown files and archive paths are never extracted.


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

The initial negative controls intentionally avoid disputed Edition 5 order
semantics. ORC/OBR-specific controls are added only after the exact profile has
resolved Issue #9. A green local qualification therefore requires both a
zero-error baseline and positive detection of every frozen negative control.
