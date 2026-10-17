# Path B third-source census — private double-omission triage

**Status: development-only intake, NOT an independent requirements denominator.**

The two original locked Edition 5 Common+NG+FRU extractions can identify
their *observed union*. A requirement that both readers omitted is absent
from that union, even if their apparent observed agreement is 100%. The
independent scope reviewer should therefore prepare a **separate**, blind
source-level R/C census, using the same pinned guide and December 2024
errata. It must not be derived from the first two submitted lists.

## Coordinator procedure

Keep all real original extractions, lock files, source evidence and census
in access-controlled storage outside the repository. Verify rights to
access the guide and errata, as well as conflicts and independent reviewer
identity, through the real institutional approval process. The neutral
starting point is
`qualification/hl7v2/required_element_review/examples/third_source_census_blank.json`.
It contains **zero** requirements and all 12 scope areas **UNREVIEWED**.
Do not commit a completed census containing reviewer identities or source
records to GitHub. The blank template deliberately fails intake while its
reviewer ID is `TO_BE_ASSIGNED`.

Only after actual source review, give each independent R/C candidate a
unique `CEN-...` ID, the precise source locus, `usage: R` or `usage: C`,
its bounded coverage area, verified source-page references, and an explicit
condition for C. Scope areas marked `SOURCE_PAGES_CHECKED` must have
source page references. Every one of the 12 areas remains present, even
if not reviewed. Fields use page numbers rather than reproducing the
copyrighted official text.

In a *private* coordinator environment with an installed package, run:

```sh
python qualification/hl7v2/required_element_review/triage_independent_source_census.py \
  reviewer-a.yaml reviewer-a.lock.json \
  reviewer-b.yaml reviewer-b.lock.json \
  independent-source-census.json private-census-triage.json
```

The script reconstructs the existing unadjudicated handoff from **both
original, byte-exact locked reviewer submissions**, verifies that the
census refers to the pinned PDF/errata, checks all 12 scope areas, enforces
distinct reviewer pseudonyms, and checks the proposed R/C rows. Outputs
are written by exclusive file creation: an existing original or report
is never overwritten.

## How to interpret output

- `candidate_rule_ids_missing_from_both`: distinct third-source rule IDs
  whose exact *locus* occurs in neither first-round list. This is a
  **candidate double-omission warning**, not automatically a validated
  omitted requirement.
- `candidate_loci_missing_from_both`: unique physical fields with such
  candidate warnings. Different conditional rules sharing a field are
  **not counted as one requirement**.
- `same_locus_rule_ids_requiring_source_comparison`: the third-source
  record's field appears in at least one original, but the original may
  have a different binding, requirement or condition. **It is not an
  adjudicated match.**
- `unreviewed_source_areas`: bounded source areas that the third reviewer
  has not yet checked; a missing area can never be inferred complete.
- `census_candidate_rule_count`: **only** the number of proposed
  third-source records, *not* an independently certified R/C denominator.

The tool deliberately **cannot** assign the scientific denominator or change
qualification. Every output fixes:
`independently_established_requirements_denominator=null`,
`human_adjudication_performed=false`,
`reviewer_independence_verified_by_software=false`,
`standards_completeness_certified=false`,
`G1_qualified=false`, and `confirmatory_permission=false`.

A distinct pseudonym is not proof of a separate qualified individual.
A filled scope row or citation is not proof that the original guide
was completely read. An independent expert must resolve *all* apparent
agreements, missing-from-both candidates, conditional distinctions and
errata conflicts, then substantiate a complete independent denominator.
The PI must separately approve any future G1 qualification and protocol
amendment. No clinical study, sealed case access, expert contact, or
external distribution is performed by this utility.
