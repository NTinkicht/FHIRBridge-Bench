# Edition 5 validation-contingency proposal (PRE-FREEZE, NOT APPROVED)

Status: **proposal only**. This document is not an amendment in force, does not
replace the tooling manifest's machine-profile gate, and does **not** authorize
confirmatory inference or opening the sealed expert set.

## Why this is needed

The selected target is HL7 v2.5.1 LRI Edition 5, with December 2024 errata,
in the general laboratory `LRI_Common_Component_V3` +
`LRI_NG_Component_R1` + `LAB_FRU_Component` combination, candidate
`LRI_NG_FRU_Profile_V3`.

The archived authoritative Edition 5 publication package is documented in
`qualification/hl7v2/results/edition5-publication-package-inspection.json`.
Its two entries are PDFs, not a machine-readable NIST/IGAMT validation bundle.
A standards participant separately reported on October 11, 2026 that the
Edition 5 guide had not been maintained in IGAMT and identified an
Edition-5-reflecting newborn-screening profile in the APHL GVT toolscope.
That communication is **private correspondence**, not a redistributable
standards artifact or public proof that no archived Edition 5 bundle exists.
Do not commit the email text, headers, or personal details to this public repo.

Authoritative public publication references:

- [HL7 LRI Edition 5 product brief](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=279)
- [December 6, 2024 errata notice](https://standups.hl7.org/2024/12/06/errata-publication-of-hl7-version-2-5-1-implementation-guide-laboratory-results-interface-lri-edition-5-us-realm/)

## Path A: exact machine-profile qualification (preferred)

Continue to accept an independently authenticated original Edition 5 +
2024DEC profile and its full companion bundle, if it can be acquired.
Preserve cryptographic identity, source lineage, selected component identity,
value-set bindings, parser/runtime dependency hashes, positive and
expected-locus negative controls, and the frozen warning/alert policy.
Do **not** substitute an older NIST LRI profile or a vendor-specific profile.

This path retains the original external-profile-valid structural gate,
provided all other protocol safeguards also pass.

## Path B: independently extracted bounded conformance (candidate)

If no qualified original bundle can be acquired after a documented search,
a **separate and explicitly labeled** measurement stratum may be proposed:

1. Fix the exact published Edition 5 + 2024DEC input PDFs and file hashes.
2. Independently extract all applicable Common, NG, and FRU requirements
   within the predeclared ORU^R01 scope. Extractors see the publication,
   not Renderer A/B code, each other's answers, or model outputs.
3. Reconcile reviewer disagreements using the public normative material,
   recording unresolved usages, datatypes, predicates, vocabulary bindings,
   lengths, and conditional constraints instead of guessing.
4. Establish a machine-readable requirements inventory with exact page/table
   pointers, coverage status, and a hash for every accepted rule.
5. Implement deterministic validators solely for fully resolved,
   independently agreed rules, with disjoint author/reviewer responsibilities
   and a separately qualified test oracle. Unknown rules never default to
   nonblocking.
6. Pass positive fixtures and targeted negative controls at their expected
   violation loci. Demonstrate a source-grounded, semantically faithful target
   representation for **each** retained primary family. Independently inspect
   coverage gaps, statuses, specimens, MSH-21, ORC, and OBR.
7. If accessible, inspect the APHL newborn-screening GVT profile strictly as
   a *differential corroboration artifact* for overlapping requirements.
   Newborn-specific requirements cannot be imported into the general-lab
   target. Preserve exact profile source, scope, and hashes if exporting is
   permitted.
8. Require independent clinical-interoperability, HL7 v2 conformance, and
   statistical-methodology review of the resulting scope and measurement
   interpretation before adopting any revision.

The correct output label under Path B is **'passes independently
reconstructed bounded Edition 5 rules'**, never **'certified against the
original Edition 5 machine-readable profile'**. A generic structural parser
pass alone is insufficient even for Path B.

## Primary endpoint and denominator safeguards

The existing primary Valid-but-Unfaithful Rate (VUR) is conditioned on
structural validity, so the definition of `VALID` is **measurement critical**.
A bounded reconstructed-rules gate is not automatically interchangeable with
full external-profile validity:

- Before any Path B activation, amend the structural-validity estimand,
  hypothesis, endpoint labels, warning policy, and analysis/preregistration
  text. State explicitly that conformance outside the reviewed bounded
  ruleset is *not assessed*.
- Preserve `VALID`, `INVALID`, `MEASUREMENT_FAILURE`, and
  `POLICY_UNRESOLVED` states, with the gate's provenance in every record.
  Unresolved conformance evidence stays `POLICY_UNRESOLVED`; it must not
  enter a VUR denominator.
- Report every attempted output and separate rates for bounded validity,
  unassessed/indeterminate conformance, invalidity, and measurement failure.
  Preserve all-attempt Valid-and-Faithful Yield (VFY) with its revised label.
- Use a predeclared scope/coverage matrix and quantify the share of required
  elements actually covered. Do not claim a percentage before independent
  extraction is complete.
- Pilot-derive verifier acceptance thresholds, preserve the sealed-test
  boundary, and prospectively freeze the selected profile-qualification path.
- If the original exact machine profile later appears, run a prespecified
  comparison as a sensitivity/differential study; never silently reclassify
  post-hoc outcomes under the earlier primary estimand.

## Go/no-go decision

Path B is **not selected by this proposal**. Before replacing any current
`acquire_exact_machine_readable_profile_bundle` blocker, require:

- an externally reviewable full Common + NG + FRU extraction and adjudication;
- pinned implementation hashes and independent positive/negative validation;
- a revised, preregistered VUR/VFY estimand and structural warning policy;
- evidence that all 11 retained LAB families are feasible under the scoped
  instrument, or a preregistered scope change before sealed-data access;
- recorded independent reviewer and statistical sign-off;
- an explicit new protocol version, freeze-readiness test changes, and a
  documented decision on whether confirmatory claims must be narrowed.

Until those steps are complete, **every existing profile acquisition, tooling,
pilot, reviewer, sealed-set, and model-execution blocker remains in force**.

Companion machine-readable proposal:
`benchmark/lri_edition5_contingency_proposal.yaml`.
