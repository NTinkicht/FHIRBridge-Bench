# Novelty Boundary

Status: **Draft — requires literature verification before Protocol v1.0**

## Safe central novelty target

The project is intended to contribute a **validated, source-grounded semantic-fidelity measurement instrument for HL7 v2 ↔ FHIR transformations**, with the FHIR → HL7 v2 direction used as the primary stress test.

The durable contribution is the ability to distinguish and measure, at fact level:

- unsupported fabrication;
- semantic corruption;
- required omission;
- licensed normalization;
- licensed derivation;
- declared representational loss;
- indeterminate mappings.

The verifier itself must be validated against blinded expert adjudication and seeded faults before it is used to support headline model comparisons.

## Claims that are intentionally NOT novel

FHIRBridge-Bench will not claim novelty for:

- LLM generation of FHIR;
- HL7 v2 → FHIR conversion;
- existence of FHIR → HL7 v2 conversion;
- deterministic interoperability mapping;
- validator-guided repair;
- constrained/schema-guided generation;
- use of FHIR Provenance;
- FHIR benchmarks in general;
- the observation that syntactic validity and semantic correctness can diverge.

## Stronger candidate novelty statement

Subject to final literature verification:

> FHIRBridge-Bench introduces and validates a source-grounded, contract-based measurement instrument for element/fact-level semantic fidelity in LLM-generated HL7 v2 ↔ FHIR transformations, including explicit treatment of fabrication, corruption, omission, and representational loss in the under-evaluated FHIR → HL7 v2 direction.

This statement must be weakened if prior work is found that materially overlaps the combination.

## Novelty threats to monitor

The literature review must continuously monitor:

- 2025–2026 LLM-to-FHIR generation studies;
- FHIR validation/repair systems;
- semantic-equivalence frameworks for structured clinical transformation;
- FHIR → HL7 v2 academic evaluations;
- source-grounded provenance/faithfulness metrics;
- deterministic HL7 transform validators;
- FHIR/OMOP and other bidirectional healthcare-standard mapping studies;
- software-engineering work on semantic equivalence, differential testing, and metamorphic testing.

## Scope discipline

The paper should read as a **measurement-science study**.

The following must remain secondary or out of scope unless independently justified:

- privacy-preserving ML;
- general cybersecurity benchmarking;
- multi-model consensus;
- chain-of-thought comparisons;
- production deployment claims;
- general-purpose provenance ontology design;
- attempts to define a replacement reverse HL7 implementation guide.

## Safe wording principles

Prefer:

- “under-evaluated” over “unexplored”;
- “to our knowledge” only after documented search;
- “validated measurement instrument” over “ground truth”;
- “projectability contract” over “reverse mapping standard”;
- “semantic fidelity relative to the declared contract” over “clinical correctness”;
- “external validation” over “real-world proof”.

## Evidence freeze

Before manuscript submission, this document must be updated with:

1. the final systematic novelty search date;
2. the closest prior works;
3. exact overlap/difference statements;
4. the final safe novelty sentence used in the abstract and introduction.
