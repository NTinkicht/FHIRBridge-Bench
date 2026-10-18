# Path B — Independent expert assignment and protected evidence custody

**Status:** Unassigned, pre-freeze coordinator plan. Not an invitation, an approval,
an ethics determination, an attested reviewer roster, or a request to meet.
This is **coordinator-only** and must **not** be sent to blinded readers.
No person has been appointed or has agreed to review by publication of this
document.

## Scientific question and scope

The bounded target is FHIR R4 → HL7 v2.5.1 ORU^R01 for **LRI Edition 5 (May
2024) with December 2024 errata**, restricted to the general-laboratory
`LRI_Common_Component_V3 + LRI_NG_Component_R1 + LAB_FRU_Component` slice.
The primary requirement extraction, independent audit and bounded G1 rule
qualification are still unfinished. The unavailable Edition 5 IGAMT
authoring export is not a prerequisite to *development*.

The objective of the external review is to independently establish the
applicable normative requirements and clinically meaningful correctness,
**not** to endorse the team's existing renderer or to provide an automated
full-profile certification.

## Assignment sequence

| Role ID (unassigned) | Capability and independent assignment | Initial deliverable | Earliest access |
| --- | --- | --- | --- |
| STD-A | HL7 v2.5.1/LRI ORU^R01 implementation and lab-interface interpretation; no knowledge of provisional rule inventory | First blind Common+NG+FRU rule inventory, with exact guide/errata evidence and UNKNOWN where appropriate | Normative documents + neutral blind extraction ZIP only |
| STD-B | A second independently sourced extraction channel; preferably a **different qualified human**; an AI-assisted first channel may be disclosed but **never labeled a human expert** | Independently locked second inventory (no STD-A output) | Same neutral inputs; isolated from STD-A |
| STD-ADJ | Different qualified human standards adjudicator; must independently inspect missing loci, every disagreement and source-grounded agreements | Signed human dispositions and explicit source-completeness/errata audit | After both first-round submissions are immutably retained |
| CLIN-1 | Lab medicine/LIS professional familiar with reports, specimen, status, units, clinical risks | Blind first-round clinical error labels on prespecified pilot cases | After scope/instrument review; no verifier predictions |
| CLIN-2 | Independent lab professional with similar domain expertise | Second complete independent blind labels, not selectively assigned by verifier discordance | Same pilot set; isolated from CLIN-1 |
| CLIN-ADJ | Independent adjudicator of clinical disagreements (subject to institutional feasibility) | Preserved conflict resolutions with clinical rationale | After both first-round clinical labels are locked |
| STATS | Applied statistician conversant with paired binary outcomes and cluster dependence | Prospectively reviewed VFY primary estimand, secondary conditional VUR, sample size and analysis plan | Draft aggregate design; no sealed outcomes |
| PI/COORD | Research investigator / evidence custodian; **not a substitute independent scientific reviewer** | Independence screening, artifact-byte verification, private custody, approvals and documented audit trail | Restricted, role-appropriate |

One person must not independently extract and subsequently represent
themselves as an independent adjudicator of **their own** rules. Where an
adjudicator has prior relevant authorship, implementation involvement, or
access to unblinded materials, document and assess the conflict; choose a
separate reviewer when independence cannot be substantiated.

## Screening before appointment (keep privately)

Record consent/availability and the actual scope, **without inventing an
agreement**. Screen (a) firsthand HL7 LRI or laboratory reporting experience,
(b) published-author/implementation/project involvement and other conflicts,
(c) ability to work independently from the benchmark code, (d) willingness
and permitted handling of the licensed official standards PDF, (e) feasible
deliverable and effort, (f) institutional ethics/compensation rules, and
(g) ability to preserve a blind first-round record. Require the person to
actually attest or sign the relevant conflict/access fields: a code-generated
checkbox is not proof of independence.

Research collaborators who help develop the mapping or G1 rule oracle can
provide **technical advice**, but must not be casually relabeled as blinded
independent judges of the same content.

Store all real names, contact details, conflicts, signed disclosures, payments,
access lists and original responses in restricted institution-approved storage,
**not in public GitHub issues/PRs or the neutral reviewer ZIP**. Public repo
material should contain process definitions and synthetic examples only.

## Provenance-controlled preparation before sending anything

1. Obtain the official Edition 5 guide and December 2024 errata from authorized
   sources. Use `verify_source_documents.py` to match **both local PDF bytes**
   to the pinned hashes; do not distribute or post those PDFs beyond license
   permissions. Archive the coordinator-side verification report privately.
2. Obtain the neutral reviewer artifact from the successful GitHub Actions job
   `lri-edition5-blind-extraction-<run_id>`, or rebuild with
   `qualification/hl7v2/required_element_review/build_blind_packet.py`.
   Verify the ZIP SHA-256 and its content manifest before distribution.
3. STD-A and STD-B receive only verified official normative documents and the
   neutral ZIP. Specifically **exclude** provisional project rule inventory,
   reference renderer code/outputs, AI extraction notes, previous reviewer
   submissions, contract hypotheses and model conclusions.
4. Capture each initial submission in private custody; independently hash the
   original bytes using `lock_responses.py`. Timestamp/attest custody outside
   the code. Never overwrite a first-round response with a correction.
5. After the first-round locks exist, create an unadjudicated review worksheet
   with `build_adjudication_handoff.py` once that tool is merged. Its
   observed rule union is **not** the independent normative denominator.
6. The separate human STD-ADJ checks disagreements, evidence in reported
   agreements, possible requirements omitted by **both** readers, every
   applicable mandatory/conditional rule in scope, and errata effects.
   Retain unresolved or excluded requirements with explicit dispositions.
7. Only after human source-completeness review may the independently reviewed
   bounded rule set enter G1 rule-level positive and expected-locus negative
   tests and all-11-family feasibility qualification. A separate scientific
   and statistical/PI freeze decision is required before confirmatory runs.

## Hold points and explicit non-authorizations

- **No reviewers have been recruited, screened or appointed**.
- **No independent Edition 5 extraction or adjudication has been received**.
- **No independent bounded-profile denominator or all-R/C completeness evidence**.
- **No G1 qualified-pass claim, no full original IGAMT profile claim**.
- **No sealed evaluation, confirmatory inference, external emails, payment,
  institutional ethics assumption or deployment**.

This coordination plan is consistent with `docs/path_b_independent_reviewer_handoff.md`,
`docs/lri_required_element_extraction_protocol.md`,
`benchmark/path_b_bounded_coverage.yaml` and
`benchmark/protocol_freeze_gates.yaml`. The separate sealed expert
`expert_validation/examples/reviewer_roster_template.yaml` is **not** the same
as the preliminary standards extractor assignment list and must not be
marked `locked_preopening` based on this plan.
