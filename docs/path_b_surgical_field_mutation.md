# Path B synthetic HL7 expected-locus mutation audit

`src/fhirbridge/path_b_surgical_mutation.py` compares **two externally supplied synthetic HL7 text artifacts** and demonstrates that they differ in precisely one existing field at an explicitly named locus (`ORC-3`, `OBR-4`, `MSH-21`, etc.).

This is **not** a normative Edition 5/2024DEC rule, a positive-message validity check, a G1 validation result, or a negative-control verdict. The module refuses missing/inserted fields, changed segment order, duplicate target segments, no-op mutations, mutations touching more than one field and mislabeled target loci. It understands the MSH field-number offset (MSH-1 is the `|` separator) but does not adjudicate profile OIDs or coded values.

Returned `SurgicalMutationEvidence` includes the original and mutated artifact hashes and the exact changed locus. It always reports `G1_qualified=false`, `validator_expected_locus_failure_confirmed=false`, and `primary_endpoint_eligible=false`.

To progress a control to qualified G1 evidence, an independently source-grounded, scope-complete Edition 5+errata requirements inventory, two locked original readings, a distinct adjudicator, original positive and negative artifacts, an actual independent validator result **at the expected field**, and external approval are still required. None is supplied or simulated by this synthetic diff utility.

The intended use is negative-control **construction QA** only; tests are synthetic fixtures. It does not change the Protocol v1 freeze ledgers or the verifier's outcome taxonomy.
