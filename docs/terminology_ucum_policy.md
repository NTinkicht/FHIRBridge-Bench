# Terminology, UCUM, and Structural-Validation Policy

Status: **Draft candidate pins — must be frozen before confirmatory inference**

## Purpose

FHIRBridge-Bench treats terminology, unit conversion, and structural validation as versioned dependencies of the measurement instrument. A semantic-fidelity decision must be reproducible from locally available, pinned content wherever possible. Live network services may support audit or differential checking, but they are not accepted as the sole confirmatory oracle.

This policy applies to the primary FHIR R4 / US Core laboratory → HL7 v2.5.1 LRI ORU^R01 slice.

## Core principles

1. **Exact code-system identity is preferred.** A source and target coding are directly equivalent only when the code and code system match, unless the frozen projectability contract explicitly licenses a mapping.
2. **Hierarchy proximity is not equivalence.** A broader, narrower, parent, child, or semantically related terminology concept is not automatically counted as equivalent.
3. **Mappings must be explicit and versioned.** `CODE_TRANSLATE` is permitted only through a frozen approved mapping artifact, named ConceptMap, or equivalent reviewed rule recorded in the contract.
4. **Unit conversion is joint value–unit reasoning.** A unit change is faithful only when the value is transformed consistently and the conversion is supported by the pinned UCUM implementation/content.
5. **Live APIs are supporting evidence, not ground truth.** Confirmatory scoring must remain reproducible if an external terminology server is temporarily unavailable or changes behavior.
6. **Structural validity and semantic fidelity remain separate.** Passing the FHIR validator or an HL7 v2 profile validator does not establish semantic preservation.

## Candidate terminology/content pins

The following versions are candidate dependencies as of the Protocol v1 drafting phase. They become immutable only when the protocol freeze commit is tagged.

### LOINC

- Candidate content version: **LOINC 2.83**.
- LOINC 2.83 was released on 19 August 2026.
- The official LOINC FHIR Terminology Service can expose LOINC content through FHIR R4, but the service is explicitly documented as **BETA** and may change or be unavailable.
- Therefore the public LOINC terminology service is an **audit/differential service only** for confirmatory FHIRBridge-Bench analysis.
- Confirmatory code validation should use a locally versioned LOINC 2.83 content snapshot or another reproducible local distribution permitted by the LOINC license.
- LOINC content usage and redistribution must respect the current LOINC license and attribution requirements.

Official evidence:
- https://loinc.org/news/loinc-version-2-83-release-highlights/
- https://loinc.org/kb/api/fhir/
- https://loinc.org/license/

### UCUM

- Candidate content version: **UCUM 2.2**.
- Candidate essence revision date: **2024-06-17**.
- The canonical development content is the UCUM `ucum-essence.xml` representation associated with those identifiers.
- The specific local UCUM implementation used for confirmatory conversion is **not yet frozen**.

Official evidence:
- https://github.com/ucum-org/ucum/blob/main/ucum-essence.xml
- https://ucum.org/

### HL7 Terminology (THO)

- Candidate terminology package: **HL7 Terminology 7.4.0**.
- The published package identifies itself as version 7.4.0 and active as of 2026-09-22.
- For FHIR R4 validation, the R4-compatible package form is preferred where the validator/package resolver requires it.

Official evidence:
- https://terminology.hl7.org/
- https://terminology.hl7.org/7.4.0/en/downloads.html

## FHIR structural validator candidate pin

For the confirmatory structural-validity path, the current candidate is:

- `org.hl7.fhir.validator-wrapper` **1.0.82**
- underlying `org.hl7.fhir.core` **6.10.0**

The 1.0.82 release explicitly reports the update to core 6.10.0. The validator must be run locally against frozen package dependencies rather than depending on mutable network lookups during confirmatory scoring.

The exact package set, package versions, command line, Java/runtime version, and checksums of validator artifacts must be captured in the frozen tooling manifest.

Official evidence:
- https://github.com/hapifhir/org.hl7.fhir.validator-wrapper/releases
- https://github.com/hapifhir/org.hl7.fhir.core

## HL7 v2 structural/profile validation

The HL7 v2.5.1 LRI Edition 5 structural/profile validator is **not yet pinned**.

Before Protocol v1.0 freeze, the project must select and document a validator or validation path that can independently assess the chosen ORU^R01 target profile as far as available tooling permits. The selection must record:

- tool/project name;
- exact version/commit;
- profile/constraint artifacts used;
- whether LRI Edition 5 + 2024DEC errata are fully, partially, or not natively supported;
- command/configuration;
- known blind spots;
- local reproducibility instructions.

Until this is resolved, development parseability checks must **not** be described as full LRI conformance validation.

## Code-equivalence policy

For a coded clinical fact, the confirmatory verifier may return semantic equivalence only under one of these conditions:

1. exact code + exact code system;
2. exact canonicalized code-system identity plus exact code;
3. a frozen approved mapping explicitly referenced by the applicable projectability rule;
4. an expert-reviewed contract rule defining a permissible representation change.

The following are insufficient by themselves:

- identical display strings;
- lexical similarity;
- embedding similarity;
- ontology graph distance;
- shared ancestor/descendant relationship;
- an LLM statement that two codes are equivalent;
- a live `$translate` response that is not tied to a frozen approved mapping/version.

If a mapping cannot be reproduced from the frozen dependency set, the case is `INDETERMINATE` for confirmatory automatic scoring rather than guessed.

## UCUM quantity-equivalence policy

For quantities, equivalence is evaluated jointly over value and unit.

A source quantity `(v_s, u_s)` and target quantity `(v_t, u_t)` may be considered equivalent when:

- the units are identical and the numeric values satisfy the rule-specific tolerance; or
- the contract licenses `UNIT_CONVERT`, the pinned UCUM implementation establishes dimensional compatibility, and converting one quantity into the other's unit yields the target value within the frozen tolerance policy.

A unit label change without a consistent numeric conversion is a semantic corruption.

Before `UNIT_CONVERT` is enabled for confirmatory scoring, the selected local UCUM implementation must pass:

- official/maintainer-provided UCUM functional tests where available;
- a project-specific laboratory conversion matrix containing expected equivalent and non-equivalent pairs;
- regression tests for common laboratory units used in the benchmark;
- negative tests for dimensionally incompatible units;
- deterministic repeated-run checks.

Every unit-equivalence decision must retain machine-readable evidence containing at least the source value/unit, target value/unit, UCUM content version, implementation/version, operation, and tolerance rule.

## Terminology-provider separation

The semantic verifier consumes a terminology-provider interface; standards lifters and renderers must not make hidden terminology-equivalence decisions.

Provider outputs used during confirmatory scoring must record:

- provider implementation name/version;
- terminology content/package version;
- local artifact hash where applicable;
- mapping identifier/version for translations;
- operation performed;
- result and evidence.

The provider must not fall back silently from a failed local lookup to a live mutable API.

## Network policy

### Confirmatory scoring

- Local/offline-first.
- No dependency on an unversioned public terminology response.
- Network access disabled where practical after all frozen dependencies are cached.
- Any unavoidable remote dependency must be version-addressable, logged, and declared in the protocol before confirmatory inference.

### Development / audit

Live services may be queried to:

- detect discrepancies;
- compare local behavior with official services;
- investigate terminology updates;
- support standards-evidence review.

Such responses are never retroactively used to alter the confirmatory contract after model outputs are seen.

## Version and hash provenance

Every confirmatory run must record the frozen tooling manifest hash plus, where applicable:

- LOINC content version and local snapshot hash;
- UCUM version/revision and local essence hash;
- HL7 THO package/version/hash;
- FHIR validator wrapper/core versions and artifact hashes;
- FHIR package versions and hashes;
- HL7 v2 validator/profile versions and hashes;
- terminology/UCUM implementation versions;
- project contract and verifier versions.

## Licensing and release hygiene

The repository may publish metadata, code, checksums, and reproducibility instructions without assuming that every terminology distribution may be redistributed unchanged.

Before public release:

- verify the redistribution terms of each external terminology/content artifact;
- include required LOINC attribution/license notices;
- use package-manager retrieval or user-supplied local content where redistribution is restricted or unclear;
- keep restricted/non-redistributable content out of Git history.

## Freeze gate

`benchmark/tooling_versions.yaml` remains `candidate` until all of the following are satisfied:

- LOINC content version and acquisition method frozen;
- local terminology provider implementation frozen;
- UCUM content and implementation frozen and qualified;
- THO package/version frozen where applicable;
- FHIR validator artifact/package set frozen with checksums;
- HL7 v2 structural/profile validator or validation path frozen and limitations documented;
- all required licenses/attribution documented;
- development regression tests pass with the exact frozen dependency set.

No dependency version may be silently upgraded after confirmatory inference begins. Any change requires a protocol amendment and separate sensitivity analysis where scientifically relevant.
