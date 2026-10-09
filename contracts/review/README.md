# External contract-review scoring

The review assignment is generated with:

```bash
python contracts/review/build_assignment.py
```

After two external reviewers independently complete responses that conform to
`contract_review_response.schema.json`, validate and compare them with:

```bash
python contracts/review/score_pair.py reviewer-a.yaml reviewer-b.yaml
```

The command rejects schema-invalid or incomplete reviews before calculating
agreement. It also requires explicit accept/reject coverage of every proposed
operation for every reviewed rule.

The generated report preserves reviewer order, records SHA-256 hashes of both
original response documents, reports raw agreement, Cohen's kappa and Gwet's
AC1, and lists every rule-level disagreement requiring adjudication.

The report never changes either review and does not adjudicate disagreements.
Original reviewer responses remain the scientific evidence.
