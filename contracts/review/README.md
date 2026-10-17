# External contract-review scoring

The current pre-freeze review target is Contract **v0.3.0**.

Generate the blind Stage-1 assignment with:

```bash
python contracts/review/build_assignment.py
```

The generated assignment is written to:

```
contracts/review/generated/contract-review-assignment-v0.3-blind.json
```

## Stage 1: blind independent classification

Each reviewer must return a response conforming to:

```
contracts/review/contract_review_blind_response.schema.json
```

Stage 1 deliberately withholds the study team's proposed target locus,
projectability label, allowed operations, equivalence rule, failure type,
severity, and renderer behavior. Reviewer conflicts/project involvement and LRI
authoring involvement are disclosed in the response.

After two external reviewers independently complete blind responses, validate
and compare them with:

```bash
python contracts/review/score_pair.py reviewer-a.json reviewer-b.json
```

Agreement is computed **only from the original blind labels**. The command
rejects incomplete responses and refuses proposal-aware Stage-2 responses as
agreement inputs. The resulting report preserves canonical SHA-256 hashes of
both source responses and reports raw agreement, Cohen's kappa, Gwet's AC1, the
confusion matrix, and all rule-level disagreements.

## Stage 2: proposal-aware critique

Only after a reviewer's Stage-1 response has been retained and hashed may the
study proposal be revealed. Stage-2 responses conform to:

```
contracts/review/contract_review_unblinded_response.schema.json
```

The Stage-2 response must record the SHA-256 of the locked blind response.
Stage-2 critique covers proposed target loci, operations, equivalence rules, and
severity. It can inform adjudication but never replaces the original Stage-1
label used for inter-rater agreement.

The report never adjudicates disagreements or rewrites either review. Original
reviewer responses remain the scientific evidence.
