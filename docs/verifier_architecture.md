# Semantic Verifier Architecture

Status: **Draft — Protocol v0.1**

## Purpose

The semantic verifier is the central measurement instrument in FHIRBridge-Bench. Its job is **not** to decide whether a generated artifact resembles a reference serialization. Its job is to determine whether clinically relevant target facts are supported by the source canonical facts under the frozen projectability contract.

The verifier is intentionally separated from benchmark generation, rendering, prompting, and model inference so that measurement does not silently inherit the assumptions of a system under test.

## Non-negotiable separation

The primary data flow is:

```text
Canonical Clinical Fact Graph
          |
          | independent renderers
          v
   FHIR / HL7 v2 source artifact
          |
          | system under test
          v
   Generated target artifact
          |
          | independent target lifter
          v
 Reconstructed target fact graph
          |
          | semantic verifier + frozen contract
          v
  Fact-level verification decisions
```

The following components must not share transformation implementation code:

1. canonical scenario generator;
2. FHIR renderer;
3. HL7 v2 renderer;
4. FHIR lifter;
5. HL7 v2 lifter;
6. semantic verifier.

Shared low-level parsing or schema libraries are allowed. Shared mapping functions are not.

## Why lifting is required

FHIR and HL7 v2 permit different but semantically equivalent serializations. Scoring target strings directly would penalize legitimate variation and would reward agreement with one reference renderer.

Therefore the verifier compares **canonical facts**, not byte strings or exact target paths. Target paths are retained as evidence and for error localization, but correctness is determined at the semantic-fact level.

## Structural validation and semantic verification are separate

Every output receives two independent assessments:

### Structural assessment

Examples:

- FHIR JSON parsing;
- FHIR R4 / profile validation;
- HL7 v2 parsing;
- HL7 v2 message/profile conformance;
- cardinality and datatype checks.

### Semantic assessment

Examples:

- required canonical fact preserved;
- grounded value unchanged except for licensed normalization;
- code semantically equivalent under an approved mapping source;
- value/unit pair jointly equivalent under UCUM;
- patient/specimen/report relationships preserved;
- unsupported clinical content not introduced;
- permitted loss explicitly distinguished from required omission.

A structurally valid artifact may fail semantic verification. This distinction defines the primary study endpoint.

## Inputs

The verifier consumes:

- source canonical graph;
- lifted target canonical graph;
- frozen projectability contract version;
- target structural-validation result;
- terminology/UCUM service results where required;
- optional model-claimed provenance, stored separately from verified grounding.

The verifier must never require a deterministic reference target artifact to score correctness.

## Lifter contract

A lifter converts a target representation into candidate canonical facts and evidence paths.

Each lifted fact should minimally expose:

```yaml
lifted_fact_id: string
fact_type: string
semantic_payload: object
target_paths:
  - string
relationships:
  - relation_type: string
    target_fact_id: string
parser_warnings: []
```

A lifter must not classify the fact as correct or incorrect. Classification belongs exclusively to the semantic verifier.

## Matching / grounding stage

For each source and target fact, the verifier constructs candidate grounding edges using only pre-declared semantic keys and contract rules.

Candidate keys may include:

- patient identifier + namespace;
- report identity within the scenario;
- coded concept equivalence;
- observation concept + temporal context + report membership;
- specimen identifier;
- explicit graph relationships.

The grounding algorithm must not use model-emitted provenance as proof. Model claims may be compared with independently established grounding afterward.

Ambiguous one-to-many or many-to-one matches are retained as ambiguity objects rather than greedily resolved when the contract does not define a unique equivalence class.

## Decision classes

Primary semantic error classes:

- `FABRICATION`
- `CORRUPTION`
- `OMISSION`
- `MISATTRIBUTION`

Non-error / non-primary classes:

- `LICENSED_NORMALIZATION`
- `LICENSED_DERIVATION`
- `DECLARED_LOSS`
- `INDETERMINATE`

Structural errors are recorded separately as `STRUCTURAL_ERROR` and do not replace semantic classifications that can still be determined.

## Deterministic precedence

When one target fact could otherwise create multiple labels, apply:

1. `MISATTRIBUTION`
2. `CORRUPTION`
3. `OMISSION`
4. `FABRICATION`

Example: a glucose result with the correct value but attached to the wrong patient is `MISATTRIBUTION`, not a fabrication for one patient plus omission for another.

Separate unrelated omissions and fabrications may still coexist in the same transformation.

## Machine-readable evidence

Every semantic decision must be reproducible from an evidence object. A decision should record:

- verifier version;
- contract version and rule ID;
- source fact ID(s);
- lifted target fact ID(s);
- source semantic payload;
- target semantic payload;
- target path(s);
- allowed operation considered;
- terminology / UCUM evidence where applicable;
- relationship evidence;
- classification;
- severity rule applied;
- whether the case is primary-endpoint eligible;
- deterministic rationale code;
- optional human-readable explanation generated from structured evidence.

Human-readable prose is not the authoritative evidence.

## Equivalence modules

The initial verifier should expose independent equivalence modules for:

### Identifier equivalence

- value preservation;
- namespace/assigning-authority preservation;
- declared namespace transforms only.

### Coded-concept equivalence

- exact system+code;
- explicitly approved ConceptMap equivalence;
- no equivalence inferred solely from display text.

### Quantity equivalence

- value + unit evaluated jointly;
- UCUM conversion when licensed;
- numerical tolerance defined per contract, not ad hoc.

### Temporal equivalence

- instant vs interval semantics;
- source precision preservation;
- time-zone normalization without instant drift;
- allowed precision reduction only if declared.

### Relationship equivalence

- patient attribution;
- report/result membership;
- specimen/result membership;
- order/report relationships where in scope.

### Status equivalence

- explicit contract status maps;
- no silent inference of finality.

## Claimed versus verified provenance

For the optional provenance-constrained model arm:

```text
model claim: source path -> operation -> target path
                    |
                    v
             independent verification
                    |
         +----------+----------+
         |                     |
      verified              rejected
```

Report claimed trace precision and recall only as secondary outcomes. The primary semantic metrics use independently verified grounding regardless of whether the model emitted a trace.

## Failure envelope

The verifier must explicitly report cases it cannot reliably score. Initial expected limitations include:

- unrestricted free-text clinical equivalence;
- local terminology with no approved mapping source;
- ambiguous FHIR component/panel to v2 OBX topology;
- cross-message longitudinal context outside the scenario graph;
- institution-specific business semantics absent from the study contract.

Such cases become `INDETERMINATE` or are excluded by scope before confirmatory evaluation. They must not be silently forced into an error/non-error class.

## Qualification sequence

Before confirmatory LLM experiments:

1. validate lifters on independently rendered reference artifacts;
2. audit alternate-but-equivalent serializations;
3. run seeded single-fault qualification;
4. run multi-fault precedence tests;
5. freeze verifier code + contract version;
6. open sealed expert-validation set;
7. estimate sensitivity, specificity, PPV, NPV, and agreement for major fidelity errors;
8. audit false positives and false negatives;
9. apply the pre-registered instrument-acceptance gate.

If the gate fails, downstream model-comparison results are exploratory.

## Anti-Goodhart rule

The confirmatory generation strategies must not receive semantic-verifier feedback and then be scored by that same verifier as headline evidence. Syntax-validator repair is allowed because structural validation is a distinct construct. A future semantic-repair study would require an independent evaluation design.

## Versioning / freeze

The following must be pinned before sealed expert validation:

- canonical schema version;
- contract version;
- lifter versions;
- verifier commit hash;
- terminology/UCUM service versions or snapshots where feasible;
- severity rules;
- decision schema;
- primary endpoint definition.

Post-freeze changes require a protocol amendment and, when they affect measurement, a new sealed evaluation set.