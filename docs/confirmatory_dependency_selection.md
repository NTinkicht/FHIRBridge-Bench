# Confirmatory Dependency Selection Notes

Status: **candidate, not frozen**

This note records tooling decisions made before the sealed expert set is opened. It does not claim that the selected tools are already qualified for confirmatory scoring. Qualification evidence, exact artifact hashes, exported profile bundles, and passing functional tests remain required by `benchmark/tooling_versions.yaml`.

## HL7 v2 structural validation path

FHIRBridge-Bench will use a **local, pinned NIST-profile validation path** for the primary structural-validity oracle rather than a hosted web validator.

Candidate stack:

- HL7 target: HL7 v2.5.1 Laboratory Results Interface (LRI), Edition 5, with 2024DEC errata.
- Wrapper: `gov.cdc:lib-hl7v2-nist-validator:1.5.0`.
- Wrapped NIST validation libraries: 1.7.3, as documented by the CDC project.
- Runtime target: Java 17.
- Profile source: an IGAMT-2-exported XML resource bundle for the exact in-scope LRI ORU^R01 profile.
- Confirmatory execution: local/offline, with the exported profile and all validator artifacts hashed and archived.
- Hosted GVT/Valitheus validation: audit/differential role only.

### Why this path was selected

NIST describes IGAMT as producing machine-computable XML conformance profiles and describes validation as comparing an HL7 v2 message instance against constraints in that XML profile. The CDC wrapper is specifically designed to run the NIST HL7 v2 validator against IGAMT profile bundles and can load profile files from local resources. This gives the study a reproducible, profile-driven validation path without relying on a mutable hosted service during confirmatory scoring.

The hosted NIST GVT infrastructure moved to a new Prometheus Computing host in September 2026. That service remains useful as an independent audit/differential comparator, but a network-hosted service is not the primary confirmatory oracle because server-side profile/runtime changes would be harder to freeze and reproduce.

### Required before freeze

The following are still mandatory:

1. obtain/export the exact LRI Edition 5 + 2024DEC-errata ORU^R01 IGAMT XML resource bundle used by the study;
2. archive all required XML files (for example `PROFILE.xml` and any applicable constraints/value-set/co-constraint/slicing files);
3. record SHA-256 for the complete profile bundle and validator artifact;
4. run the clean reference messages and structural-negative controls through the local validator;
5. document how ERROR/WARNING results map to the study's binary structural-validity outcome;
6. compare a development subset against the hosted GVT/Valitheus service as a differential check;
7. retain all disagreement reports and resolve profile/version mismatches before instrument freeze.

Until these steps are complete, `Hl7V251OruDevelopmentValidator` remains a development sanity gate only and must not be described as LRI Edition 5 conformance validation.

## FHIR structural validation path

FHIRBridge-Bench will use the HL7-maintained FHIR validator locally with the exact R4 and US Core packages required by the study.

Candidate package/runtime set:

- FHIR release package: `hl7.fhir.r4.core#4.0.1`.
- US Core package: `hl7.fhir.us.core#9.0.0`.
- US Core's published terminology dependency: `hl7.terminology.r4#7.1.0`.
- Validator wrapper candidate: `org.hl7.fhir.validator-wrapper:1.0.82` with core 6.10.0.
- Runtime target: Java 17.
- Confirmatory execution: local, with package caches and validator artifacts frozen before scoring.
- Public/hosted validator services: audit/differential only.

US Core 9.0.0 is the published STU 9 guide and is based on FHIR R4 4.0.1. Its published ImplementationGuide resource identifies `hl7.fhir.us.core#9.0.0` and the R4 terminology dependency `hl7.terminology.r4#7.1.0`. The semantic terminology layer may separately freeze a later HL7 Terminology release, but the structural validator must retain the package dependency used by the actual US Core 9.0.0 publication unless a documented compatibility experiment justifies an override.

Before freeze, the exact validator artifact, runtime, package files/cache, command line, network policy, and validation-result mapping must be archived and hashed. A clean development sample and structural-negative controls must pass the qualification procedure before `profile_validation_qualification_passed` can be set true.

## UCUM quantity-equivalence path

FHIRBridge-Bench will use a **local UCUM service backed by the frozen UCUM essence file** for transformations where the reviewed contract explicitly licenses unit conversion.

Candidate stack:

- UCUM specification/content: version 2.2.
- `ucum-essence.xml`: frozen local artifact; exact SHA-256 still unresolved.
- Implementation: `org.fhir:ucum:1.0.10`.
- Confirmatory role: local quantity validation and conversion only when the contract explicitly permits `UNIT_CONVERT`.
- Exact unit identity remains valid without invoking conversion.

The FHIR Ucum-java library exposes validation, comparability, and conversion services over a supplied `ucum-essence.xml`. Version 1.0.10 is newer than the 1.0.9 release that patched the published XML external-entity vulnerability affecting versions below 1.0.9.

### Qualification requirements

The provider is not frozen merely because a Maven coordinate has been selected. Before confirmatory use:

1. freeze and hash the exact UCUM 2.2 essence file;
2. run the official UCUM functional test file and archive results;
3. run a project-specific laboratory conversion matrix covering every conversion pair licensed by the frozen projectability contract;
4. verify joint value+unit conversion, not unit-string equivalence alone;
5. establish numeric precision/tolerance policy before the sealed set is opened;
6. fail closed to `INDETERMINATE` when a conversion is unsupported or ambiguous;
7. archive implementation version, Java runtime, essence hash, test-suite hash, and qualification report.

No display-string similarity, lexical similarity, embedding similarity, or hierarchy proximity may be substituted for UCUM quantity equivalence.

## Public evidence used for this candidate decision

- US Core 9.0.0 home/package identity: https://hl7.org/fhir/us/core/index.html
- US Core 9.0.0 ImplementationGuide dependencies: https://hl7.org/fhir/us/core/STU9/ImplementationGuide-hl7.fhir.us.core.html
- FHIR R4 downloads/package information: https://hl7.org/fhir/R4/downloads.html
- HL7-maintained FHIR validator core repository: https://github.com/hapifhir/org.hl7.fhir.core
- HL7 validator wrapper repository: https://github.com/hapifhir/org.hl7.fhir.validator-wrapper
- HL7 LRI Edition 5 product brief: https://www.hl7.org/implement/standards/product_brief.cfm?product_id=279
- NIST Healthcare Data Interoperability & Productivity Platform: https://www.nist.gov/itl/health-it-testing-infrastructure/health-it-testing-infrastructure/nist-healthcare-data
- NIST GVT transition information: https://www.nist.gov/itl/nist-health-it-program-legacy-website/gvt
- CDC HL7v2 NIST Validator wrapper: https://github.com/CDCgov/lib-hl7v2-nist-validator
- Maven Central CDC validator 1.5.0: https://central.sonatype.com/artifact/gov.cdc/lib-hl7v2-nist-validator
- FHIR Ucum-java: https://github.com/FHIR/Ucum-java
- Maven Central `org.fhir:ucum:1.0.10`: https://central.sonatype.com/artifact/org.fhir/ucum
- UCUM release artifacts: https://ucum.org/docs/artifacts
- UCUM functional tests: https://ucum.org/docs/functional-tests

## Scientific boundary

These selections reduce implementation ambiguity but do **not** establish semantic ground truth. Structural validators answer conformance questions; UCUM answers quantity-equivalence questions. Neither is allowed to decide whether an unsupported clinical fact was fabricated, whether a required source fact was omitted, or whether the projectability contract itself is correct. Those remain separate parts of the FHIRBridge-Bench measurement design.
