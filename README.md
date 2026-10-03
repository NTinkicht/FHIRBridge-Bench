# FHIRBridge-Bench

**Valid Is Not Faithful: Source-Grounded Semantic Verification of LLM-Based HL7 v2–FHIR Transformations**

FHIRBridge-Bench is a research project on **semantic fidelity measurement for AI-assisted healthcare interoperability**. The project does not treat schema validity as proof of correctness and is not intended to introduce another generic HL7/FHIR converter.

The central research objective is to determine whether structurally valid HL7 v2 ↔ FHIR transformations preserve the clinical meaning of their source, and to build a reproducible, independently validated verifier for detecting **fabrication, semantic corruption, omission, licensed transformation, and declared representational loss**.

## Scientific focus

- **Primary stress direction:** FHIR → HL7 v2
- **Control direction:** HL7 v2 → FHIR
- **Primary methodological contribution:** a source-grounded semantic-fidelity verifier validated against blinded expert adjudication
- **Primary empirical question:** how often do structurally valid transformations remain semantically unfaithful?
- **Core principle:** claimed provenance is not accepted as verified provenance

## Current phase

The repository is currently in the **Protocol v1.0** phase. Before large-scale LLM experimentation begins, the project will freeze:

1. the research question and primary hypothesis;
2. the primary endpoint;
3. the canonical clinical fact representation;
4. the semantic/projectability contract;
5. the error taxonomy and precedence rules;
6. the verifier validation protocol;
7. the benchmark and statistical analysis plan.

Large-scale model inference will begin only after the measurement framework and its validation criteria are frozen.

## Planned artifact structure

```text
FHIRBridge-Bench/
├── docs/                # protocol, novelty boundary, statistics, governance
├── contracts/           # semantic/projectability contracts
├── canonical/           # canonical clinical fact representation
├── benchmark/           # scenarios, profiles, perturbations, manifests
├── renderers/           # independent FHIR and HL7 v2 renderers
├── verifier/            # structural + semantic verification
├── fault_injection/     # seeded semantic faults
├── expert_validation/   # blinded verifier-validation protocol
├── models/              # model adapters/prompts/configs (later phase)
├── experiments/         # registered experiments (later phase)
├── analysis/            # statistical analysis
├── tests/               # regression and instrument-validation tests
└── results/             # released aggregate results
```

## Research discipline

This project will explicitly avoid the following claims unless independently demonstrated:

- that LLM-to-FHIR generation is novel;
- that HL7 v2-to-FHIR mapping is novel;
- that FHIR-to-HL7 v2 conversion itself is novel;
- that structural validity implies semantic fidelity;
- that round-trip equality is a sufficient correctness criterion;
- that the verifier constitutes clinical ground truth;
- that synthetic benchmark performance establishes deployment safety.

## Status

**Protocol v1.0 drafting in progress.**

The methodology, benchmark-generation rules, verifier acceptance criteria, and analysis plan will be versioned before model evaluation begins.
