# Seeded-fault development batch

This directory materializes deterministic **development-only** seeded-fault stimuli used to exercise FHIRBridge-Bench before the verifier is frozen.

Run:

```bash
python qualification/faults/build_development_batch.py
```

The current batch contains 314 deterministic stimuli:

- 50 FABRICATION
- 50 OMISSION
- 50 MISATTRIBUTION
- 64 CORRUPTION across eight mutation operators
- 100 MULTI_FAULT cases cycling MF001–MF003

The generated JSON records the graph hash and deterministic fault-manifest hash for every case. These cases are instrument-development evidence only. They are not a substitute for independently authored faults or the blinded expert-validation set, and their expected labels must not be used to tune the sealed evaluation after freeze.
