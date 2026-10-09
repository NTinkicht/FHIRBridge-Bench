# Local LOINC 2.83 qualification

FHIRBridge-Bench does not commit or redistribute the licensed LOINC release files.

1. Log in to the official LOINC website and download **Loinc_2.83.zip**.
2. Keep the archive outside the repository.
3. Run:

```bash
python qualification/loinc/qualify_release.py /absolute/path/to/Loinc_2.83.zip
```

The command verifies the official release filename and vendor-published MD5, computes SHA-256 for the ZIP and canonical `LoincTable/Loinc.csv`, and checks the frozen benchmark subset against LOINC 2.83.

The official LOINC 2.83 archive contains a second byte-identical copy at `AccessoryFiles/PanelsAndForms/Loinc.csv`. Qualification accepts duplicate `Loinc.csv` members only when they are byte-identical; any conflicting duplicate fails closed.

A successful result is written to `qualification/loinc/results/loinc-2.83-qualification.json`. Only the hashes and qualification report should be committed. Do **not** commit the LOINC ZIP or CSV.

The live LOINC FHIR terminology service remains audit-only; it is not the confirmatory ground-truth dependency.
