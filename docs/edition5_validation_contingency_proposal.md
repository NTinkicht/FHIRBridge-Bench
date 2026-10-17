# Edition 5 Path B development decision and qualification proposal (PRE-FREEZE)

**PI decision (2026-10-11): Path B is the preferred DEVELOPMENT route.**
This authorizes work on a bounded, independently extracted Edition 5 ruleset
and its review materials; it does not mean that rules, structural-validity
estimand, error classification, clinical instrument, or confirmatory protocol
have been independently qualified. The formal prospective endpoint amendment
is still **draft/unapproved**. The existing machine-profile freeze blockers
are not removed until an explicit alternative qualification gate with
independent evidence is implemented and approved. No confirmatory inference
or sealed-set opening is authorized.

## Why this is needed

The selected target is HL7 v2.5.1 LRI Edition 5, with December 2024 errata,
in the general laboratory `LRI_Common_Component_V3` +
`LRI_NG_Component_R1` + `LAB_FRU_Component` combination, candidate
`LRI_NG_FRU_Profile_V3`.

The archived authoritative Edition 5 publication package is documented in
`qualification/hl7v2/results/edition5-publication-package-inspection.json`.
Its two entries are PDFs, not a machine-readable NIST/IGAMT validation bundle.
Unpublished custodian/standards correspondence received on October 11 and
14, 2026 reports that Edition 5 was **never codified in IGAMT**, while an
older laboratory-suite GVT scope exists but remains private during QA.
A separate APHL newborn-screening profile reportedly reflects some Edition 5
requirements, but is not a general-laboratory Edition 5 ground-truth export.
These are **private provenance reports**, not redistributable standards
artifacts or public proof that no independent non-IGAMT archive exists.
Accordingly, development must not wait for an original Edition 5 IGAMT bundle.
Do not commit email text, headers, identities or personal details to this
public repository.

Authoritative public publication references:

- [HL7 LRI Edition 5 product brief](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=279)
- [December 6, 2024 errata notice](https://standups.hl7.org/2024/12/06/errata-publication-of-hl7-version-2-5-1-implementation-guide-laboratory-results-interface-lri-edition-5-us-realm/)

## Path A: exact machine-profile qualification (optional sensitivity)

If an independently authenticated original Edition 5 + 2024DEC profile
and its full companion bundle becomes available, retain it for a **prespecified
differential/sensitivity analysis**, not as an indefinite prerequisite to
Path B development.
Preserve cryptographic identity, source lineage, selected component identity,
value-set bindings, parser/runtime dependency hashes, positive and
expected-locus negative controls, and the frozen warning/alert policy.
Do **not** substitute an older NIST LRI profile or a vendor-specific profile.

This path can support a separate original-profile conformance claim after its
own qualification. It must not silently relabel Path B primary cases.

## Path B: independently extracted bounded conformance (selected for development)

The PI has selected development of a **separate, explicitly labeled** bounded
measurement stratum, without waiting indefinitely for the original bundle.
It remains unqualified until the full prospective amendment is approved:

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

**Path B has been selected only as the preferred development direction.**
The investigator has NOT approved replacing the current conformance gate,
freezing a new endpoint, or opening confirmatory data. Before replacing any current
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

## Minimum-resource independent-review design (candidate; not expert evidence)

A clean-context AI extractor may prepare **reader A** from the pinned PDF, and
a standards-qualified human may independently prepare **reader B** blind to
the AI response and repository inventory. This is not equivalent to two
independent human extractors: retain AI-assisted provenance, risks of
correlated standards interpretation, exact first-round replies, and perform
separate human adjudication of **every disagreement plus a predeclared
random sample of agreements**. The proposed 10–15% agreement audit rate is
a planning hypothesis, not certification of requirements coverage.
The final fraction must be justified before handoff.

The proposed primary scope covers MSH, PID, ORC, OBR, OBX, SPM and NTE if
used, including applicable group, cardinality, field/component, value-set,
conditional and cross-field assertions. **Do not assume every R/C element
has been found until a reviewer has certified the denominator.**

The expert label study should separate (1) unprompted clinically meaningful
source-to-target differences, (2) contract classification, (3) blinded verifier
comparison and (4) contract blind-spot review. Do not use verifier disagreement
alone to trigger the second human label.

## Primary-outcome redesign for statistical review (candidate, NOT frozen)

Conditional VUR remains scientifically useful for description, but the paired
*both-arms-valid* comparison subset can depend on treatment strategy. A
candidate primary endpoint is all-attempt **valid-and-faithful yield (VFY)**
for a prespecified contrast. A companion all-attempt
**valid-and-unfaithful** risk captures unsafe passing outputs. Do not
preregister a hypothesis rewarding increased unsafe-valid outputs.

A fully explicit outcome partition must track structurally invalid,
structurally unassessable, semantically indeterminate, valid-faithful and
valid-unfaithful cases. Bounded G1 validity is distinct from full Edition 5
machine-profile conformance; syntax-only G0 cannot masquerade as G1.

Not fixed by direction approval: primary contrast/model count, effect size,
sample size, multiplicity, enrichment weights, missingness/abstention,
and independent statistical review.

## Path B development milestone ordering

1. Pin official normative publication and errata hashes; check copyright
   constraints before redistribution.
2. Prepare separate blind extraction packets and collect AI reader A and
   human reader B, with separate human adjudication and completeness audit.
3. Construct the bounded ruleset with positive/expected-locus negative
   controls and explicit out-of-scope and unresolved requirement coverage.
4. Independently demonstrate feasibility across the 11 LAB families with
   provisional development messages, without using Renderer A as truth.
5. Qualify a separate G0 grammar check and G1 bounded rule oracle.
   Unresolved mandatory requirements never silently become passes.
6. Complete blind contract and clinical review, pilot sensitivity/PPV on
   naturally occurring model errors, then independent statistical review.
7. Only then freeze the amended endpoint and warning policy; preregister,
   authorize and execute sealed confirmatory evaluation.
