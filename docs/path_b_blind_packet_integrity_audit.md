# Path B — mechanical integrity audit of the blind reviewer packet

**Status: pre-freeze packet hygiene only.** This audit does not verify the official guide/errata PDFs, any licensing permission, reviewer independence, scientific completeness, HL7 v2.5.1 conformance, or G1 qualification.

After `qualification/hl7v2/required_element_review/build_blind_packet.py` prepares the neutral ZIP, run:

```sh
python -m qualification.hl7v2.required_element_review.audit_blind_packet
```

The audit independently reads the completed ZIP and its generated manifest. It compares **all three allowed entries** byte-for-byte against the current checked-out schema/template and the neutral generated README, validates the entire ZIP's digest, checks each member digest and length, pins the exact official publication SHA-256 values and Common+NG+FRU slice, and rejects:

- added, missing or duplicate entries, including hidden extra files or ZIP path variants;
- unsafe ZIP member forms, encryption, symlinks, oversized files, or unexpected compression;
- altered ZIP payloads, even when an attacker edits the manifest hashes to match;
- altered source and errata identities, publication-scope claims, or unexpected manifest keys;
- obvious leaked implementation inventory, renderer or mapping artifacts;
- any claim in the manifest that independent review, original-profile conformance, or approval has already occurred.

A green audit produces `lri-edition5-blind-extraction-integrity.json`, **without opening or bundling licensed normative PDFs**. It is archived alongside the neutral ZIP and manifest in GitHub Actions. The JSON records ZIP byte count and checksum plus the names checked; it unconditionally contains `G1_qualified=false`, `independent_extraction_received=false`, `official_source_pdfs_verified_or_licensed=false`, and `external_distribution_authorized=false`.

The audit compares against the current checked-out expected inputs, not a separately signed, immutable build-root attestation. It therefore detects accidental build/package drift and many tampering cases **but does not independently prove the checkout itself is trustworthy**. PI/custodian must still verify repository provenance, source PDF bytes, licensed distribution rights, expert conflicts and independent assignment. No external requests are sent and no raw reviewer submissions are opened.

Protocol freeze and all currently missing independent Edition 5 extraction/adjudication requirements remain blocked.
