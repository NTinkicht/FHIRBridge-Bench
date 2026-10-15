# Path B — 11-family pre-freeze development feasibility census

**Purpose:** Produce traceable synthetic **development** evidence while
external HL7 v2.5.1 LRI Edition 5 + December 2024 errata extraction,
adjudication and bounded G1 qualification remain absent.

**Not a G1 validator, clinical assessment, completed FHIR external-validator
report, benchmark endpoint estimate, or confirmatory feasibility sign-off.**

## Reproduce

Run in a clean repository checkout with the pinned research environment:

```bash
python qualification/hl7v2/report_path_b_family_feasibility.py
```

The command fails rather than quietly exclude a family or change the expected
order-renderer behavior. Its JSON report is written to
`qualification/hl7v2/results/path-b-11-family-prefreeze.json`.
GitHub Actions archives this result under an artifact named
`path-b-eleven-family-development-<run_id>`. Check the
workflow run/commit SHA when interpreting it.

## What is actually assessed

Each of LAB-001 through LAB-011, on its own **development** seed, must have:

1. One independently authored synthetic canonical order and diagnostic report,
   and an authored order identifier.
2. A FHIR R4 renderer output with `ServiceRequest` and
   `DiagnosticReport.basedOn` explicitly connected.
3. A lifted FHIR representation judged `FAITHFUL` by the
   **draft** projectability policy, without primary-eligible
   fabrication/corruption/omission/misattribution.
4. An explicit **fail-closed rejection** from the still-unqualified HL7 v2
   order-context Renderer A. Unqualified HL7 serialization is never counted
   as progress and instead fails the census.

The JSON preserves hashes of the scenario specification, draft mapping
contract and blocked protocol gate ledger. Its rows declare that the G1
qualified family count and confirmatory permission are zero. Separate
GitHub Actions FHIR validation steps may supply evidence of FHIR validation,
but this report never claims to execute that validator itself.

The LAB-012 ambiguity family is **not** a primary family and is not included.

## Remaining real feasibility work

The HL7 v2 side currently fails closed by design, so **zero families can be
reported as independently qualified for the primary structural-validity
endpoint**. Source-grounded positive fixtures and per-rule expected-locus
negative fixtures cannot be called G1-qualified until independent human
Common+NG+FRU requirements extraction and source-completeness adjudication
establish the bounded profile oracle, including applicable conditions,
terminology, MSH-21 identity, ORC/OBR identifiers and status semantics.

After a distinct, reviewed bounded G1 oracle is approved for development,
a **separate** future qualification procedure must show source-grounded
HL7 v2 serialization and expected-locus negative controls for all eleven
families. No scientific gate, scoring denominator, preregistration or sealed
dataset should be changed just because this development report completes.

This artifact remains **development-only** and intentionally refuses to run
if the freeze policy or confirmation permission changes.
