# Bounded Path B rule-evidence scaffold (pre-freeze)

This is a **mechanical evidence register only**, not an HL7 v2.5.1 LRI Edition 5+2024DEC rule oracle, source completeness certification, or an authorized G1/confirmatory validator.

## Structure

- `src/fhirbridge/path_b_rule_evidence.schema.json` defines the source identity, selected Common+NG+FRU component slice, independently sourced rule IDs, applicability, condition, required/conditional usage, page/errata anchors, original locked response references, distinct adjudicator, and rule-specific positive and expected-locus negative controls.
- `src/fhirbridge/path_b_rule_evidence.py` crosschecks immutable normative publication byte hashes and the *still blocked* protocol/coverage ledgers. It refuses to report if Path B is silently promoted, and reports missing sources, unresolved/disputed rules, absent independent coverage denominator, missing original reviewers, or untested rule loci.
- `qualification/hl7v2/required_element_review/examples/path_b_rule_evidence_dev_template.json` is an **unassessed developer-only example**, explicitly not an expert extraction or complete Edition 5 denominator. Source pages in this template are pointers for future independent review, not the results of that review.
- `qualification/hl7v2/report_path_b_rule_evidence.py` emits JSON `qualification/hl7v2/results/path-b-rule-evidence-prefreeze.json` via `python qualification/hl7v2/report_path_b_rule_evidence.py` from an installed checkout.

## Scientific safeguards

A valid schema merely confirms a record's format. Synthetic reviewer pseudonyms, references and SHA-256 values in unit tests **do not certify authenticity, expertise, blinding, independence, or actual source completeness**. Real locked reviewer response files and identities remain in access-controlled institutional storage, not this public repository.

Rule evaluation reports `G1_qualified=false` and `confirmatory_permission=false` **unconditionally**. Even an artificially complete sample rule can never promote itself. This tool makes no changes to the existing LRI renderer, verifier outcome taxonomy, frozen analysis protocol or confirmatory permission. G1 can only be designed and separately qualified after **independent** source extraction, double-omission audit, errata adjudication, controls at correct loci, clinical/technical review and final PI methodology approval.

Do not add substantive source-extracted R/C rules or real reviewer records to this template before their approved provenance and custodial route are established. In particular, MSH-21's conflicting printed pre-coordinated OIDs remain DISPUTED; neither candidate is chosen by this scaffold.
