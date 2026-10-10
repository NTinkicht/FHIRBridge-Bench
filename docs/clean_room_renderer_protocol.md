# Clean-Room Reference Renderer Protocol

Status: **Draft — Protocol v0.1**

## Purpose

FHIRBridge-Bench uses two reference renderers to expose ambiguity in the projectability contract and to reduce the risk that benchmark generation encodes one preferred serialization. The renderers are **not ground truth** and agreement between them does not validate the canonical fact graph.

## Independence objective

Renderer A and Renderer B must implement the same frozen canonical-fact and projectability specifications without sharing mapping implementation code.

The intended independence is methodological rather than merely organizational:

- common input: frozen canonical clinical fact graph;
- common specification: frozen projectability contract and named standards/profile sources;
- different implementation code;
- different transformation modules;
- preferably different technical stacks or libraries;
- no copying of mapping tables/functions between renderers;
- no use of LLM-generated mapping code;
- no inspection of the other renderer's output during initial implementation.

## Allowed shared dependencies

The renderers may share only non-semantic infrastructure such as:

- canonical schema definitions;
- generic YAML/JSON loading;
- standards parsers/serializers;
- generic logging;
- run-manifest schemas;
- structural validators invoked after rendering.

They must not share:

- fact-to-FHIR mapping functions;
- fact-to-HL7 v2 mapping functions;
- terminology translation logic beyond invoking the same independently specified terminology service;
- status lookup implementation tables unless the table itself is a frozen external artifact named by the contract;
- projectability decisions not present in the frozen contract.

## Implementation declaration

Each renderer must publish a machine-readable declaration containing:

- renderer ID and version;
- developer/agent identity used for implementation;
- implementation language and major libraries;
- standards/profile sources consulted;
- contract version consumed;
- terminology/UCUM dependencies;
- date implementation began;
- statement that the other renderer's implementation and rendered outputs were not consulted before the first differential run.

## Suggested separation

A defensible initial design is:

### Renderer A

- Python-oriented implementation;
- explicit semantic mapping modules authored from the contract text;
- independent FHIR/v2 serializers.

### Renderer B

- Java/HAPI-oriented or otherwise technically distinct implementation where practical;
- mapping implementation authored independently from the same frozen contract;
- no import of Renderer A source code or fixtures except canonical-input examples approved as shared protocol fixtures.

The exact stacks may change, but code-level independence must remain demonstrable.

## Contract synchronization point for order-context work

Before either renderer implements the Edition 5 order-context amendment, the
canonical order facts, source FHIR profile, projectability rules, and structural
requirements must exist in one numbered contract revision. Renderer A and
Renderer B must receive that same revision as the semantic specification.

Renderer A may be exercised against development validators while the contract
is still draft, but any semantic change learned from validator feedback must be
written back into the contract and independently reviewed before Renderer B is
asked to implement it. Renderer B must never be expected to infer a rule from
Renderer A output, Renderer A source, or an undocumented validator workaround.

Once the order-context contract revision is designated as the differential
synchronization point:

- both renderers receive the same canonical schema, contract revision, profile
  selection record, and permitted standards evidence;
- neither renderer receives the other renderer's source or rendered outputs;
- if Renderer A changes semantic behavior after that point, the contract must
  either already authorize the behavior or be amended and re-synchronized;
- a contract amendment affecting order semantics requires both renderers to be
  re-run from that amended specification before differential comparison;
- qualification fixes that merely correct serialization without changing the
  frozen semantic mapping must be documented as such.

This synchronization rule is intended to prevent an asymmetry in which Renderer
A is iteratively taught hidden profile behavior while Renderer B sees only a
later, undocumented interpretation.

## Differential comparison

Once both implementations independently pass structural validation on the development corpus, run a differential comparison.

For each canonical fact/scenario, classify renderer agreement as:

- `SEMANTICALLY_EQUIVALENT_SERIALIZATION`
- `DIFFERENT_BUT_CONTRACT_PERMITTED`
- `CONTRACT_AMBIGUITY`
- `RENDERER_A_DEFECT`
- `RENDERER_B_DEFECT`
- `BOTH_DEFECTIVE`
- `INDETERMINATE`

Disagreement must never be resolved by majority vote among Renderer A, Renderer B, and an external converter.

## External differential converters

Microsoft FHIR Converter, CDC PRIME, LinuxForHealth, or other relevant converters may be run as external differential comparators where their input/output assumptions match the selected scenario.

Their outputs may:

- reveal a contract ambiguity;
- reveal missing local variation;
- provide an additional implementation perspective;
- identify renderer defects.

Their outputs may **not**:

- define the benchmark gold serialization;
- automatically settle a disagreement;
- create a new projectability rule after model outputs are observed.

## Contract amendment path

If a renderer disagreement reveals that the frozen draft contract is underspecified during development:

1. create a contract-disagreement record;
2. record both implementations' interpretations without changing them first;
3. trace the ambiguity to standards/profile evidence;
4. obtain independent expert adjudication where needed;
5. either amend the pre-freeze contract or mark the rule `INDETERMINATE`;
6. add a regression fixture;
7. re-run both renderers.

After Protocol v1.0 freeze, changes require a protocol amendment and must not reuse the same confirmatory set as though no change occurred.

## Renderer output requirements

Every output must include a sidecar render manifest recording:

- canonical graph ID;
- renderer ID/version;
- contract ID/version;
- target profile/version;
- rendering timestamp;
- terminology/UCUM dependency versions where available;
- structural-validation result reference;
- warnings and unsupported facts;
- declared-loss manifest where applicable.

The sidecar is audit metadata. It is not used by the verifier as proof that a mapping is correct.

## Anti-circularity rule

The lifting parser and semantic verifier must not import either renderer's semantic mapping modules. A round-trip through Renderer A followed by a lifter that reuses Renderer A's mapping code is invalid as verifier qualification evidence.

## Acceptance criteria for Issue #4

Issue #4 is complete only when:

1. both renderers independently consume canonical graphs;
2. both produce structurally valid artifacts for the agreed development slice;
3. implementation declarations are present;
4. no semantic mapping code is shared;
5. a differential-disagreement report is generated;
6. every unresolved semantic disagreement is either adjudicated or marked `INDETERMINATE`;
7. external converters, if used, are clearly labeled differential comparators rather than truth;
8. regression fixtures capture all resolved disagreement classes.
