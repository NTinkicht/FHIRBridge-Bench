# Standards Evidence Snapshot — 2026-10-03

Status: **Protocol evidence ledger; not a substitute for external profile review**

This snapshot records standards facts used to justify the first FHIRBridge-Bench laboratory study slice. It deliberately separates **verified standards evidence** from **research-team reverse-mapping decisions**.

A forward HL7 v2 → FHIR mapping does not automatically define a unique FHIR → HL7 v2 mapping. Likewise, a resource-level FHIR mapping page is indicative rather than a complete target-profile specification. Reverse-direction projectability rules remain subject to the named HL7 v2 implementation profile, the projectability contract, and external expert review.

## 1. Target HL7 v2 implementation guide

**HL7 Version 2.5.1 Implementation Guide: Laboratory Results Interface (LRI), Edition 5 — US Realm** is listed by HL7 as:

- product type: Implementation Guide;
- ballot type: STU;
- current state: Active;
- realm: US Realm;
- status date: 2024-05-16;
- responsible work group: Orders and Observations.

The HL7 product page also lists **LRI Edition 5 with 2024DEC Errata** as the current STU document. HL7 published the errata notice on 2024-12-06.

Official sources:

- https://dev3.hl7.org/implement/standards/product_brief.cfm?product_id=279
- https://dev3.hl7.org/implement/standards/product_matrix.cfm
- https://standups.hl7.org/2024/05/16/stu-publication-of-hl7-version-2-5-1-implementation-guide-laboratory-results-interface-lri-edition-5-us-realm/
- https://standups.hl7.org/tag/errata/

### Study implication

FHIRBridge-Bench may defensibly name LRI Edition 5 + 2024DEC errata as the target laboratory results profile. However, the product page does **not** provide enough field-level conformance detail to freeze every reverse-mapping rule. Exact LRI field usage/cardinality must still be checked against the actual Edition 5 guide/errata and externally reviewed before Protocol v1.0.

## 2. US Core 9.0.0 source profile

HL7 lists **US Core Implementation Guide Edition 9.0.0** as a published STU document. The selected source side is FHIR R4 / US Core 9.0.0 laboratory reporting.

Official source:

- https://dev3.hl7.org/implement/standards/product_brief.cfm?product_id=500
- https://hl7.org/fhir/us/core/STU9/
- https://hl7.org/fhir/us/core/STU9/StructureDefinition-us-core-diagnosticreport-lab.html

### Study implication

US Core 9.0.0 is a reasonable named FHIR source profile for the initial laboratory slice. Source-profile requirements are evidence about what FHIR facts exist and may need preservation; they do not determine a unique v2 serialization.

## 3. DiagnosticReport / OBR evidence

HL7's current FHIR mapping documentation identifies the following HL7 v2 correspondences for `DiagnosticReport`:

- `DiagnosticReport.code` ↔ `OBR-4`;
- `DiagnosticReport.effective[x]` ↔ `OBR-7` (with interval/end semantics involving `OBR-8` in the v2-to-FHIR IG mapping);
- `DiagnosticReport.issued` ↔ `OBR-22`;
- `DiagnosticReport.status` ↔ `OBR-25`, explicitly noted as not a 1:1 mapping;
- `DiagnosticReport.specimen` ↔ SPM segment(s);
- `DiagnosticReport.result` ↔ OBX segment(s).

The same HL7 mapping page warns that FHIR resource-level v2 mappings are indicative and are not complete without critical v2 context.

Official sources:

- https://hl7.org/fhir/6.0.0-snapshot1/diagnosticreport-mappings.html
- https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-obr-to-diagnosticreport.html

### Study implication

These mappings support candidate semantic correspondences in the contract, but the reverse rules must be scoped by LRI Edition 5. In particular:

- report status requires an explicit reverse status map;
- `DiagnosticReport.identifier` must not be naively collapsed into OBR placer/filler order identifiers;
- effective time may require interval decomposition rather than a single-field copy.

`REPORT_IDENTIFIER_MAPPING` therefore remains `INDETERMINATE` in the current contract.

## 4. Observation / OBX evidence

HL7's current FHIR mapping documentation identifies:

- `Observation.status` ↔ `OBX-11`;
- `Observation.code` ↔ `OBX-3`;
- `Observation.effective[x]` ↔ `OBX-14`;
- `Observation.value[x]` ↔ `OBX-2`, `OBX-5`, and `OBX-6` depending on value datatype;
- `Observation.interpretation` ↔ `OBX-8`;
- `Observation.referenceRange` ↔ `OBX-7`;
- `Observation.note` ↔ NTE-3 in appropriate OBX context;
- `Observation.hasMember` / `derivedFrom` relationships may depend on `OBX-4` usage;
- `Observation.component` may also require OBX-4-based containment/relationship semantics.

Official sources:

- https://hl7.org/fhir/6.0.0-snapshot1/observation-mappings.html
- https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-obx-to-observation.html

### Study implication

The verifier must compare **typed semantic values**, not raw `OBX-5` strings. `OBX-2` and `OBX-6` participate in value semantics. Value and unit must be checked jointly.

The official mapping documentation itself demonstrates why panel/component topology is not safely invertible by string reversal. `PANEL_COMPONENT_TOPOLOGY` therefore remains `INDETERMINATE` for the first confirmatory slice.

## 5. Specimen / SPM evidence

HL7's current FHIR mapping documentation identifies:

- `Specimen.identifier` ↔ `SPM-2`;
- `Specimen.type` ↔ `SPM-4` (and potentially `SPM-5` depending on context);
- `Specimen.collection.method` ↔ `SPM-7`;
- `Specimen.collection.quantity` ↔ `SPM-12`;
- `Specimen.collection.collected[x]` ↔ `SPM-17`;
- `Specimen.receivedTime` ↔ `SPM-18`;
- `Specimen.status` ↔ `SPM-20`.

Official source:

- https://hl7.org/fhir/6.0.0-snapshot1/specimen-mappings.html
- https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-spm-to-specimen.html

### Study implication

SPM-2, SPM-4, SPM-7, SPM-12, and SPM-17 are evidence-backed candidate loci for the current contract. They remain `expert_review_required: true` until LRI Edition 5 usage constraints are independently checked.

## 6. Evidence hierarchy for the projectability contract

For Protocol v0.1, evidence strength is treated as:

1. **Named target implementation profile requirement** (LRI Edition 5 + errata) — highest relevance for target legality/usage;
2. **HL7 v2-to-FHIR STU ConceptMaps / mapping guidance** — strong evidence of semantic correspondence, but direction-specific;
3. **FHIR core resource v2 mapping pages** — supporting/indicative evidence;
4. **US Core source-profile invariants** — evidence about source obligations;
5. **external deterministic converters** — differential implementation evidence only;
6. **LLM outputs** — never evidence for defining the contract.

A lower-ranked source cannot silently override a higher-ranked target-profile rule.

## 7. Explicit unresolved evidence gaps

Before Protocol v1.0 freeze, the following must be resolved or retained as `INDETERMINATE`:

- exact LRI Edition 5 required/RE/O cardinality/usage for each scored PID/OBR/OBX/SPM field;
- exact allowed status mappings for the selected LRI profile;
- report/order identifier semantics and placer/filler distinctions;
- performer/results-interpreter target loci for the initial scope;
- encounter-context requirement for the selected laboratory use case;
- component/panel topology where multiple valid OBX serializations exist;
- local code-table assumptions not covered by approved terminology mappings.

## 8. Scientific guardrail

This file is a dated **evidence snapshot**, not a reverse implementation guide. A projectability rule becomes confirmatory only after:

1. standards evidence is recorded;
2. the named target profile permits the representation;
3. the semantic equivalence class is defined;
4. independent external reviewers can classify the rule with acceptable agreement or the rule is moved to `INDETERMINATE`;
5. the contract version is frozen before confirmatory model inference.

No later agreement among an LLM and one or more converters may retroactively create a confirmatory rule.
