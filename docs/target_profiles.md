# Target Profiles for Protocol v0.1

Status: **Selected for the primary laboratory stress test; contract still draft**

## Decision summary

FHIRBridge-Bench will begin with a deliberately narrow laboratory-result workflow before adding additional message families.

### Primary stress direction

**FHIR R4 / US Core 9.0.0 laboratory reporting → HL7 v2.5.1 Laboratory Results Interface (LRI) Edition 5, ORU^R01**

### Control direction

**HL7 v2.5.1 LRI Edition 5, ORU^R01 → FHIR R4 / US Core 9.0.0 laboratory reporting**

The two directions are evaluated as asymmetric transformation tasks. Exact round-trip equality is not a correctness criterion.

---

## FHIR source profile family

The primary FHIR side is based on **FHIR R4** using **US Core Implementation Guide 9.0.0 (STU 9)**.

Core profiles for the first laboratory scope:

- US Core DiagnosticReport Profile for Laboratory Results Reporting;
- US Core Laboratory Result Observation Profile;
- US Core Patient Profile;
- supporting Encounter, Practitioner/Organization, ServiceRequest, and Specimen resources when present and in scope.

The initial confirmatory scope is standard laboratory reporting, emphasizing chemistry and hematology-style atomic and panel results.

### Deferred from the first confirmatory profile

To avoid mixing fundamentally different semantics into Protocol v1.0, the following are initially excluded from the confirmatory core and may be added as later benchmark strata:

- microbiology workflows with organism/susceptibility structures;
- clinical genomics;
- newborn dried-blood-spot screening;
- public-health-specific reporting requirements beyond the common laboratory-result core;
- institution-specific FHIR extensions without a reviewed projectability rule.

These exclusions limit the first contract; they are not claims that those domains are unimportant or unsupported by the standards.

---

### FHIR order representation

The source-side order is represented with the **US Core ServiceRequest Profile
9.0.0**, not an unconstrained base ServiceRequest. US Core 9.0.0 explicitly
profiles ServiceRequest for orders, including requester support, and the US Core
laboratory DiagnosticReport guidance states that `DiagnosticReport.basedOn`
connects the report to the originating order. The benchmark therefore uses a
source-grounded ServiceRequest plus `DiagnosticReport.basedOn` when authoring
Edition 5 order context.

Order-control, filler-order-identifier, ordering-provider identity, and
basedOn-to-ORC semantic equivalence remain outside the primary endpoint until
the relevant contract rules have completed independent review. Their presence
may still participate in the structural-validity gate where the target profile
requires it.

## HL7 v2 target profile

The primary HL7 v2 target is:

**HL7 Version 2.5.1 Implementation Guide: Laboratory Results Interface (LRI), Edition 5 - US Realm, including the published 2024DEC errata.**

The initial message family is **ORU^R01**, used for unsolicited observation/laboratory-result reporting.

For the first confirmatory general-laboratory slice, the selected pre-coordinated profile candidate is **LRI_NG_FRU_Profile_V3** (OID `2.16.840.1.113883.9.195.3.25`). It combines the mandatory Common component with the non-globally-unique identifier component and the unique filler-order-number component. This avoids inventing ISO OID semantics for the benchmark's synthetic identifiers while allowing one explicit source-grounded filler order identifier to identify each order without introducing the additional composite identity semantics of FRN.

This profile selection is a study-design choice and remains pending exact machine-readable Edition 5 + 2024DEC bundle acquisition and local qualification. It does not relax the requirement for ORC, OBR, filler order number, or ordering provider.

The target is therefore not generic “valid HL7 v2”. Every FHIR → v2 output in the primary experiment must be evaluated against the named LRI profile and the subset of that profile frozen in the projectability contract.

### Initial message structure in scope

The first contract will focus on the standard laboratory-reporting structures needed to represent the canonical facts selected for Protocol v1.0, including where applicable:

- MSH — message metadata;
- PID — patient identity/demographics;
- PV1 — encounter context when present and projectable;
- ORC — order context when required by the selected LRI profile use case;
- OBR — report/order-level laboratory context;
- SPM — specimen context when present and projectable;
- OBX — individual laboratory observations/results;
- NTE — comments only when the contract explicitly permits a narrative representation.

Exact field usage, cardinality, vocabulary constraints, and permitted alternatives are defined by the versioned projectability contract rather than by this overview document.

---

## Why laboratory ORU^R01 is the first profile

This workflow is scientifically useful because it contains several semantic dimensions that can fail while a message remains structurally valid:

- patient and order identifiers;
- coded test identity;
- numeric and coded result values;
- UCUM units;
- reference ranges;
- interpretation/abnormal flags;
- result and report status;
- clinically relevant timestamps;
- patient/report/result relationships;
- performer/specimen context;
- optional narrative content.

It therefore provides a bounded but non-trivial setting for distinguishing structural validity from semantic fidelity.

---

## External references and differential comparators

The following external systems may be used as **differential comparators**, never as ground truth:

1. **CDC PRIME FHIR Converter**
   - includes a FHIR → HL7 v2 converter and an ORU_R01 mapping schema;
   - useful for identifying implementation disagreements and reverse-mapping edge cases.

2. **Microsoft FHIR Converter**
   - supports FHIR R4 → HL7 v2 in preview using Liquid templates;
   - useful as an independently developed reverse-conversion comparator.

3. **LinuxForHealth HL7 v2 to FHIR Converter**
   - supports ORU_R01 in the v2 → FHIR direction;
   - useful as a control-direction differential comparator.

None of these converters defines correctness for FHIRBridge-Bench. Their disagreements with each other and with the clean-room reference renderers are recorded as evidence about ambiguity or implementation variation.

---

## Profile-freeze rules

Before Protocol v1.0 is tagged:

1. the exact HL7 LRI Edition 5 artifact/errata revision used by the study must be archived by citation/version identifier;
2. the exact US Core 9.0.0 profiles used by the study must be recorded by canonical URL and package version;
3. the projectability contract must enumerate the subset of facts that contribute to the primary endpoint;
4. every ambiguous reverse mapping must be classified as `INDETERMINATE` unless external evidence and expert agreement justify a stronger class;
5. implementation-specific variants must be defined as separate benchmark profiles, not silently accepted by the core profile;
6. no target-profile rule may be changed after confirmatory model outputs are examined without a protocol amendment.

---

## Standards references

- HL7 International. **HL7 Version 2.5.1 Implementation Guide: Laboratory Results Interface (LRI), Edition 5 - US Realm**, active STU, with 2024DEC errata.
  - https://www.hl7.org/implement/standards/product_brief.cfm?product_id=279
- HL7 International. **US Core Implementation Guide 9.0.0 (STU 9), FHIR R4**.
  - https://hl7.org/fhir/us/core/STU9/
- US Core DiagnosticReport Profile for Laboratory Results Reporting.
  - http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab
- CDCgov/prime-fhir-converter.
  - https://github.com/CDCgov/prime-fhir-converter
- microsoft/FHIR-Converter.
  - https://github.com/microsoft/FHIR-Converter
- LinuxForHealth/hl7v2-fhir-converter.
  - https://github.com/LinuxForHealth/hl7v2-fhir-converter

## Scope note

The profile decision is a study-design choice, not a claim that LRI Edition 5 is the universal or only valid target for FHIR → HL7 v2 laboratory conversion. The results will be explicitly scoped to the named profile and benchmark variants.