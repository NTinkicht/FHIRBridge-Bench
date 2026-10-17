# Renderer B return validation

The clean-room implementation must remain isolated until its initial source and
tests are committed. Before any comparison against Renderer A, validate the
machine-readable implementation declaration:

```bash
python renderer_validation/validate_renderer_b_declaration.py \
  path/to/renderer-b-declaration.yaml \
  --expected-inputs path/to/private-custodian-expected-inputs.yaml
```

The command first checks the declaration schema, then applies scientific
clean-room gates that cannot be expressed by shape validation alone. It blocks
comparison when Renderer A source/output was inspected, mapping code or semantic
mapping utilities were reused, accidental exposure was declared, the
declaration is incomplete, placeholders remain, or the frozen contract identity
does not match.

**LLM-generated mapping code is a blocking violation of the current scientific
clean-room independence protocol.** An AI-authored Codex prototype must declare
`llm_generated_mapping_code_used: true`, retain its prompt/context provenance,
and will produce `ready_for_differential_comparison: false`. The CLI returns
**exit status 2** when that scientific comparison gate remains blocked.

For controlled, explicitly exploratory AI-authored development comparisons,
the report includes a separate
`ready_for_exploratory_agent_comparison: true` ONLY when all other custody,
schema, identity, exposure and handoff gates are satisfied. This output never
qualifies scientific independence, G1 conformance, or confirmatory permission.
An AI mapping-code prototype requires a prospective methodology amendment and
independent review before it can be proposed as scientifically valid Renderer B.

The direct Python assessment function also validates the packaged declaration
and custodian-input schemas, rather than accepting incomplete mappings as ready
just because a CLI wrapper was skipped. A schema-valid declaration remains
necessary but not sufficient for any comparison.


## Current synchronization point

The active clean-room synchronization point is Contract `v0.3.0`.

The generated challenge package now contains source-grounded canonical order
context. Renderer B may implement the FHIR ServiceRequest/basedOn side from the
shared v0.3 specification, but the HL7 v2 Edition 5 order projection remains
explicitly unsupported/fail-closed until the exact machine-readable Edition 5
profile and blind external review resolve the remaining MSH-21/ORC/OBR details.

A returned declaration referencing Contract v0.2 is rejected by the scientific
readiness gate.
