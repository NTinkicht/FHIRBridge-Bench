# Path B all-attempt outcome accounting — prefreeze development diagnostic

**Not a preregistration, validated G1 instrument, inferential estimate, or
authorized confirmatory experiment.** This module encodes the seven
*proposed* outcome states in
`analysis/path_b_estimand_candidate.yaml`. The PI has not selected or frozen
the candidate primary VFY_G1 estimand.

## Why this work can be done before independent experts

The old conditional VUR contrast can silently select a different set of
cases under two strategies because each strategy has to produce a valid
artifact before its output enters that denominator. The candidate
all-attempt VFY comparison avoids treating increased *valid but unsafe*
output yield as improvement.

The development utility `fhirbridge.path_b_outcome_audit.audit_path_b_all_attempts`
computes descriptive counts and pairwise VFY contingency tables from
**synthetic or otherwise specifically authorized development-only inputs**.

It requires two separate inputs:
1. **Pre-run expected assignment manifest** with
   `source_instance_id`, `model_key`, `strategy` and
   `analysis_cluster_id`.
2. **Observed assignments** with exactly the same fields plus one
   `outcome` from the seven proposed partition values.

The manifest is not inferred from the observations. It must come from the
prospectively determined source/model/strategy assignment plan. Missing,
unexpected, duplicate, invalid or cluster-reassigned observations fail
closed; none is silently excluded or turned into a success. A completely
missing run must be explicitly represented as the appropriate
`STRUCTURAL_MEASUREMENT_FAILURE` or other state according to the final
approved policy; this module **does not automatically classify** missing
data.

The draft outcome partition is:
- `INVALID_G0`
- `INVALID_G1`
- `VALID_G1_FAITHFUL`
- `VALID_G1_UNFAITHFUL`
- `VALID_G1_SEMANTIC_INDETERMINATE`
- `STRUCTURAL_MEASUREMENT_FAILURE`
- `STRUCTURAL_POLICY_UNRESOLVED`

The report provides one stratum per **model and strategy**, with full
seven-state counts and all-attempt descriptive
`vfy_g1_all_attempts` and `valid_unfaithful_yield_g1_all_attempts`.
Conditional `descriptive_vur_g1` is computed on *determinate valid* cases
only and becomes `null` when that denominator is zero; unknowns and
invalids remain in the full seven-state distribution.

For each within-model pair of strategies, a complete crossed-design
manifest is required. A paired all-attempt VFY table records both succeed,
A-only succeeds, B-only succeeds and neither succeeds. There is no
post-hoc `both_arms_VALID` case selection, no McNemar p-value, no claim
about improvement and no pooling across model keys.

A stable canonical-JSON SHA-256 binds the manifest and observation record.
These are **integrity fingerprints**; they do not establish source identity,
expert truth, cryptographic signature, or clinical validity.

## Scientific boundaries

The result type hardcodes `G1_qualified=false`,
`confirmatory_permission=false` and
`approved_confirmatory_estimand=false`. Synthetic outcome fixtures are
not a substitute for an independently qualified Edition 5 conformance
gate, calibrated verifier, blinded labels, or the PI/statistician's
approved outcome and missingness policy.

**Human-only next steps:** independent statistician review of the proposed
partition, denominator and pairwise contrast; pilot-based sample-size and
acceptance thresholds; and PI approval of the prospective protocol
amendment, before sealed data are touched.
