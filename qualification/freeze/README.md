# Tooling freeze readiness

Run:

```bash
python qualification/freeze/report_readiness.py
```

The report is deliberately non-destructive. It lists every unresolved value and false qualification flag required by `benchmark/tooling_versions.yaml` before the manifest can be marked `frozen`.

A candidate report with blockers is expected during development and exits successfully so CI can archive the evidence. Confirmatory experiment code must still call `assert_confirmatory_frozen()`, which rejects any manifest that is not both fully resolved and explicitly marked frozen.
