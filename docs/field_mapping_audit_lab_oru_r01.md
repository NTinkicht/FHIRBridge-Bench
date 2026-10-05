# Field Mapping Audit: FHIR R4 / US Core 9.0.0 → HL7 v2.5.1 LRI Ed5 ORU^R01

Status: **Evidence ledger — not a frozen reverse mapping**

This document records field-level evidence used to build the FHIR → HL7 v2 projectability contract for the first confirmatory laboratory slice. It is deliberately conservative.

The official HL7 v2-to-FHIR maps are used as **evidence about semantic correspondence**, not as proof that the reverse mapping is unique or lossless. Reverse-direction rules must still be reviewed against the named HL7 v2 target profile and by external experts before Protocol v1.0 is frozen.

## Fixed study scope

- Source: FHIR R4, US Core 9.0.0 laboratory reporting
- Primary source profiles:
  - US Core DiagnosticReport Profile for Laboratory Results Reporting
  - US Core Laboratory Result Observation Profile
  - US Core Patient Profile
  - FHIR Specimen where present
- Target: HL7 v2.5.1 Laboratory Results Interface (LRI), Edition 5, ORU^R01
- Realm: US
- Initial clinical slice: general chemistry / hematology-style reports, atomic results, and simple panels

## Authoritative evidence sources

1. US Core 9.0.0 DiagnosticReport laboratory profile
   - https://hl7.org/fhir/us/core/STU9/StructureDefinition-us-core-diagnosticreport-lab.html
   - Important constraints include mandatory status/category/code/subject and conditional presence of `effective[x]` and `issued` for common report statuses.

2. HL7 Version 2 to FHIR STU1, Segment PID → Patient
   - https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-pid-to-patient.html

3. HL7 Version 2 to FHIR STU1, Segment OBR → DiagnosticReport
   - https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-obr-to-diagnosticreport.html

4. HL7 Version 2 to FHIR STU1, Segment OBX → Observation
   - https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-obx-to-observation.html

5. HL7 Version 2 to FHIR STU1, Segment SPM → Specimen
   - https://hl7.org/fhir/uv/v2mappings/ConceptMap-segment-spm-to-specimen.html

6. HL7 Version 2 to FHIR STU1, ORU_R01 message → Bundle
   - https://hl7.org/fhir/uv/v2mappings/ConceptMap-message-oru-r01-to-bundle.html

7. HL7 V2.5.1 Implementation Guide: Laboratory Results Interface (LRI), Edition 5, US Realm
   - HL7 product page / package and 2024DEC errata
   - Exact Edition 5 field usage remains an explicit independent-review requirement before freeze.

## Evidence-backed correspondences

The following correspondences are strongly supported by the published v2-to-FHIR maps. They are **candidate reverse-direction rules**, not automatic inverse mappings.

### Patient / PID

| Canonical fact | FHIR source | v2 target evidence | Current contract stance |
|---|---|---|---|
| Patient identifier | `Patient.identifier` | `PID-3` ↔ Patient.identifier | MUST_PRESERVE candidate |
| Patient name | `Patient.name` | `PID-5` ↔ Patient.name | MAY_TRANSFORM candidate |
| Birth date | `Patient.birthDate` | `PID-7` ↔ Patient.birthDate | MUST_PRESERVE candidate |

Notes:
- Identifier namespace/system handling must be explicit; preserving the value alone is insufficient when multiple assigning authorities are possible.
- Name decomposition is representational and must not be scored as corruption when semantic components are preserved.

### DiagnosticReport / OBR

| Canonical fact | FHIR source | v2 target evidence | Current contract stance |
|---|---|---|---|
| Report/order code | `DiagnosticReport.code` | `OBR-4` ↔ DiagnosticReport.code | MUST_PRESERVE candidate |
| Effective start/time | `DiagnosticReport.effective[x]` | `OBR-7` ↔ effective start/time | MAY_TRANSFORM candidate |
| Effective end | `DiagnosticReport.effectivePeriod.end` | `OBR-8` ↔ effective end | MAY_TRANSFORM candidate |
| Report issued/released time | `DiagnosticReport.issued` | `OBR-22` ↔ DiagnosticReport.issued | MUST_PRESERVE when source present and in-scope status |
| Report status | `DiagnosticReport.status` | `OBR-25` ↔ DiagnosticReport.status | MAY_TRANSFORM via explicit code map |

US Core 9.0.0 additionally requires `DiagnosticReport.effective[x]` and `DiagnosticReport.issued` for common statuses including partial, preliminary, final, amended, corrected, and appended. Therefore, silent loss of these source facts should not be treated as benign merely because the target message remains syntactically valid.

### Observation / OBX

| Canonical fact | FHIR source | v2 target evidence | Current contract stance |
|---|---|---|---|
| Observation code | `Observation.code` | `OBX-3` ↔ Observation.code | MUST_PRESERVE candidate |
| Observation value | `Observation.value[x]` | `OBX-5` ↔ Observation.value[x], conditioned by OBX-2 | MUST_PRESERVE candidate |
| Quantity unit | `Observation.valueQuantity` unit/system/code | `OBX-6` ↔ quantity unit | MAY_TRANSFORM with UCUM-equivalence check |
| Reference range | `Observation.referenceRange` | `OBX-7` ↔ reference range | MAY_TRANSFORM candidate |
| Interpretation | `Observation.interpretation` | `OBX-8` ↔ interpretation | MAY_TRANSFORM via explicit code map |
| Result status | `Observation.status` | `OBX-11` ↔ Observation.status | MAY_TRANSFORM via explicit code map |
| Observation effective time | `Observation.effectiveDateTime` | `OBX-14` ↔ effectiveDateTime | MUST_PRESERVE/MAY_TRANSFORM candidate pending LRI review |

Important constraints:
- `OBX-2` determines the representation used in `OBX-5`; the verifier must evaluate the **typed semantic value**, not only the rendered string.
- Repeating `OBX-5`, components, and panel/member relationships are not assumed to have a unique reverse serialization. These cases require equivalence-class scoring rather than string matching.
- `OBX-4` / component or relationship semantics are implementation dependent and remain outside the frozen core until LRI-specific behavior is reviewed.

### Specimen / SPM

| Canonical fact | FHIR source | v2 target evidence | Current contract stance |
|---|---|---|---|
| Specimen identifier | `Specimen.identifier` | `SPM-2` ↔ Specimen.identifier | MUST_PRESERVE candidate |
| Specimen type | `Specimen.type` | `SPM-4` ↔ Specimen.type | MUST_PRESERVE/MAY_TRANSFORM candidate |
| Collection method | `Specimen.collection.method` | `SPM-7` ↔ collection.method | MAY_TRANSFORM candidate |
| Collection quantity | `Specimen.collection.quantity` | `SPM-12` ↔ collection.quantity | MAY_TRANSFORM candidate |
| Collection time | `Specimen.collection.collected[x]` | `SPM-17` ↔ collected period/time | MUST_PRESERVE/MAY_TRANSFORM candidate |

The exact use and requiredness of SPM in the selected LRI scenario must be confirmed against LRI Edition 5 before any of these become frozen primary-endpoint rules.

## Explicitly unresolved mappings

The following must remain `INDETERMINATE` or outside the primary endpoint until independently reviewed:

1. **DiagnosticReport identifiers → OBR placer/filler/order identifiers**
   - FHIR report identifiers and v2 placer/filler identifiers can represent different business concepts.
   - Do not collapse them into one identifier rule.

2. **Encounter context**
   - `DiagnosticReport.encounter` / `Observation.encounter` may be useful but is not uniformly required for all lab result scenarios.

3. **Performer and results interpreter**
   - FHIR allows several actor types; v2 representation depends on the selected field/segment and profile semantics.

4. **Panel/component topology**
   - One FHIR Observation with components is not automatically equivalent to one OBX segment.
   - Multiple OBX segments may legitimately represent one semantic observation or panel structure.

5. **Free-text report forms and conclusions**
   - `DiagnosticReport.presentedForm`, `conclusion`, and narrative content are not part of the confirmatory atomic-result core.

6. **Local extensions and Z-segments**
   - Deferred from the first confirmatory slice.

## Reverse-mapping rule

A published v2→FHIR correspondence can support a reverse projectability rule only when all of the following hold:

1. the source FHIR fact is in the selected source profile/scenario;
2. the target v2 field is legal in the named LRI target profile;
3. the reverse operation is semantically unambiguous enough to define an equivalence class;
4. no competing v2 locus represents the same fact under the selected profile;
5. any required terminology or datatype transformation is explicitly licensed;
6. the rule has not been inferred from model output or from the output of a reference converter;
7. unresolved expert disagreement is moved to `INDETERMINATE`.

## Immediate contract updates justified by this audit

The next contract revision should add candidate rules for:

- `DiagnosticReport.effective[x]` → OBR-7 / OBR-8;
- `DiagnosticReport.issued` → OBR-22;
- `Observation.effectiveDateTime` → OBX-14;
- `Specimen.identifier` → SPM-2;
- `Specimen.type` → SPM-4;
- `Specimen.collection.method` → SPM-7;
- `Specimen.collection.quantity` → SPM-12;
- `Specimen.collection.collected[x]` → SPM-17.

These should remain `expert_review_required: true` until the LRI Edition 5 field-level audit and external contract review are complete.

## Scientific safeguard

This audit deliberately records both **supporting evidence and unresolved ambiguity**. A rule is not strengthened because an LLM, Microsoft FHIR Converter, CDC PRIME, LinuxForHealth, or either clean-room renderer happens to produce the same field. Converter agreement is useful differential evidence, not truth.
