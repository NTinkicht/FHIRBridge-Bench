# Path B: eleven-family G0/G1 development gap matrix

**Status:** PREFREEZE / DEVELOPER-ONLY / NOT SCIENTIFICALLY QUALIFIED  
**Scope:** LAB-001–LAB-011; FHIR R4 US Core 9.0.0 → HL7 v2.5.1 ORU^R01, selected LRI Edition 5 Common+NG+FRU slice and December 2024 errata.  
**Evidence basis:** checked-in scenario specification, draft contract, preliminary order diagnostics, profile-selection ledger, and the PR #27 reproducible development-feasibility runner. This is a **static engineering review**, not a new execution of external validators or an independent reading/adjudication of the normative PDFs.

## What the 11/11 figure actually establishes

PR #27 reports eleven developer FHIR render/lift round trips faithful **only under a draft verification policy** and eleven intentional HL7 Renderer A fail-closed outcomes. The report performs no external FHIR validation itself. No independently qualified bounded G1 HL7 output has been demonstrated (**0/11**). G0 syntax success is not a substitute for G1 and cannot establish correct order context.

For **every** primary family, the generator declares a source-authored order and report and the FHIR rendering is checked for exactly one ServiceRequest and one DiagnosticReport linked by `DiagnosticReport.basedOn`. Neither that relation nor presence of a source identifier proves that the source's accession, placer order ID, and filler order ID are interchangeable or assigned to the correct ORC/OBR locus.

## Family-by-family development matrix

| Family | Distinguishing source scenario | FHIR development observation | HL7 target-specific evidence still missing | Status |
| --- | --- | --- | --- | --- |
| LAB-001 | Single normal numeric result, UCUM, range and final statuses | Draft round trip only; source order and basedOn checked | ORC/OBR source-correct locus, OBR/OBX status, numeric datatype and unit mapping, conditional fields | G1 NOT QUALIFIED |
| LAB-002 | Numeric high interpretation | Same global draft round-trip check | LAB-001 gaps plus high-flag/OBX-8 interpretation and range cross-check | G1 NOT QUALIFIED |
| LAB-003 | Numeric low interpretation | Same global draft round-trip check | LAB-001 gaps plus low-flag/OBX-8 interpretation and range cross-check | G1 NOT QUALIFIED |
| LAB-004 | Coded qualitative result | Same global draft round-trip check | OBX-2/OBX-5 datatype and coded-value vocabulary binding, ORC/OBR order context | G1 NOT QUALIFIED |
| LAB-005 | Panel with 3–8 observations | Same global draft round-trip check | OBR-to-multiple-OBX grouping, observation order/identity and required cross-segment constraints | G1 NOT QUALIFIED |
| LAB-006 | Specimen ID/type/collection | Same global draft round-trip check | SPM source and field binding, namespace/collection-time fidelity and report/specimen association | G1 NOT QUALIFIED |
| LAB-007 | Preliminary report and observation | Same global draft round-trip check | Independently adjudicated OBR-25 vs OBX-11 mapping, allowable preliminary representations | G1 NOT QUALIFIED |
| LAB-008 | Corrected/amended result | Same global draft round-trip check | Independently adjudicated corrected status and version/identity preservation at OBR/OBX | G1 NOT QUALIFIED |
| LAB-009 | Offset-aware observation/report time | Same global draft round-trip check | DTM offset/instant fidelity and allowed normalization at actual v2 loci | G1 NOT QUALIFIED |
| LAB-010 | Patient/specimen namespace semantics | Same global draft round-trip check | PID/SPM assigning-authority components, role-preserving order IDs, expected-locus namespace mutants | G1 NOT QUALIFIED |
| LAB-011 | Repeated same analyte at distinct times/values | Same global draft round-trip check | Repeated OBX identity/group attribution, timing and no collapsing/reordering of source observations | G1 NOT QUALIFIED |

LAB-012 is an ambiguity/sensitivity family, **not** a primary endpoint case. This matrix does not promote it.

## Cross-cutting unresolved requirements and exact-locus controls

| Locus / rule family | What currently exists | Required evidence / control before bounded G1 | Disposition |
| --- | --- | --- | --- |
| MSH-21 profile declaration | Edition 5 publication cites two different pre-coordinated OIDs (.3.25 vs .3.3); component OIDs are provisional | Independent source+errata adjudication of applicable declaration, positive message and mutation that corrupts **MSH-21** | **UNRESOLVED**, never auto-select either pre-coordinated OID |
| ORDER_OBSERVATION group / ORC / OBR | Preliminary page-anchored candidate diagnostics check ORC count, selected required fields and OBR presence | Independent Common+NG+FRU requirement inventory; candidate positive control plus omission at the exact ORC/OBR group | **NOT G1**, candidate diagnostics cannot certify |
| ORC-1 | Draft source order is not an HL7 order-control instruction | Explicitly sourced and adjudicated derivation of control code; prohibit default/invented code; control mutates ORC-1 | **UNKNOWN / FAIL CLOSED** |
| ORC-2, OBR-2 placer | Lifter can observe assertions and preliminary comparator can identify mismatches | Source-authored role, namespace, EI components; both-place equality/applicability; fabricated placer and role-swapped negatives | **INDETERMINATE** unless independently resolved |
| ORC-3, OBR-3 filler | Candidate field-presence/equality checks | Filler role and namespace must be source-correct; distinguish source-grounding from correct locus; mutations in each field | **INDETERMINATE** pending independent mapping |
| Accession versus filler/placer | Source-authored DiagnosticReport accession may be present, but its business role is different | Deliberately distinct synthetic accession, placer and filler identifiers; record role-swapped fields as **wrong-locus evidence** distinct from source grounding; leave the semantic verdict **INDETERMINATE** until the mapping is independently adjudicated (not automatically FABRICATION or FAITHFUL) | **DO NOT CONFLATE** |
| OBR-4 order/report code | ServiceRequest.code and DiagnosticReport.code can diverge | Distinct-code fixture and adjudicated target projection; wrong-code and swapped-code controls at OBR-4 | **INDETERMINATE** |
| ORC-12 versus OBR-16 | Candidate matching diagnostics | Source-authored ordering provider, XCN component/namespace audit and field-specific mutant | **UNQUALIFIED** |
| OBR-25 versus OBX-11 | Draft status representations | Independently adjudicated report/observation status map including preliminary and corrected cases; exact-field controls | **UNQUALIFIED** |
| OBX, SPM, PID and chronology | FHIR-side draft fixtures test many facts; independent HL7 G1 remains blocked | Per-field type, cardinality, vocabulary, namespace, time-zone and cross-segment controls, with omissions and wrong-locus mutations | **INCOMPLETE** |
| Rule completeness denominator | Developer inventory is explicitly incomplete (12 development rows, not an independently audited denominator) | Two independent extraction channels, original locks, separate adjudication and double-omission audit of Common+NG+FRU and errata | **NO DENOMINATOR** |

## Suggested evidence contract for the next implementation PR

For each prospective G1 rule, store a stable rule ID, applicability including conditional predicates, declared message/profile slice, field path, source guide page/table and errata anchor, reader A and reader B original dispositions, separate adjudicator disposition, positive control, *expected-locus* negative control, and an explicit disposition among `UNASSESSED`, `UNKNOWN`, `DISPUTED`, `EXCLUDED_WITH_REASON`, and `ADJUDICATED`. Keep human-source materials in protected storage, not public GitHub. No developer-only record can transition itself to `ADJUDICATED`.

A test/report MUST refuse to label any result `VALID_G1` when (1) the complete independent denominator is absent, (2) any applicable required/conditional rule remains unresolved, (3) controls do not demonstrate failure at the intended field, (4) the applicable errata have not been covered, or (5) the protocol freeze is blocked. Store **source-grounding** and **target-locus correctness** as separate diagnostic/evidence dimensions, **not new semantic classifications**. Existing verifier classifications are `VERIFIED_EQUIVALENT`, `LICENSED_NORMALIZATION`, `LICENSED_DERIVATION`, `DECLARED_LOSS`, `FABRICATION`, `CORRUPTION`, `OMISSION`, `MISATTRIBUTION`, `INDETERMINATE` and `STRUCTURAL_ERROR`; a wrong-locus observation must map into the established taxonomy **only after** an independently qualified rule permits that inference. In unresolved cases retain `INDETERMINATE` rather than forcing `FABRICATION` or `VERIFIED_EQUIVALENT`.

## Reproduction / traceability

- `benchmark/scenarios/lab_core_v0.1.yaml`: family names, primary eligibility and mandatory fact groups
- `src/fhirbridge/path_b_development_feasibility.py`: 11-family draft FHIR round-trip and guarded HL7 report; refuses changed freeze boundaries
- `src/fhirbridge/path_b_order_diagnostics.py`: expressly non-normative preliminary ORC/OBR diagnostics
- `benchmark/lri_profile_selection.yaml`: selected Common+NG+FRU slice and MSH-21 dispute
- `benchmark/protocol_freeze_gates.yaml`, `benchmark/path_b_bounded_coverage.yaml`: blocked scientific gates and absent independent denominator
- `contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml`: unapproved draft mapping
- Issues #15 (role and order-code mapping), #16 (Path B methodological amendment), #9 (order context)

**This file is a gap register, not a proposed normative oracle, external expert opinion, qualified G1 measurement, approved amendment, or license to run sealed comparisons.**
