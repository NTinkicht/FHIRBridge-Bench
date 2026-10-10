# Renderer B return validation

The clean-room implementation must remain isolated until its initial source and
tests are committed. Before any comparison against Renderer A, validate the
machine-readable implementation declaration:

```bash
python renderer_validation/validate_renderer_b_declaration.py \
  path/to/renderer-b-declaration.yaml
```

The command first checks the declaration schema, then applies scientific
clean-room gates that cannot be expressed by shape validation alone. It blocks
comparison when Renderer A source/output was inspected, mapping code or semantic
mapping utilities were reused, accidental exposure was declared, the
declaration is incomplete, placeholders remain, or the frozen contract identity
does not match.

Use of an LLM during independent implementation is recorded as an audit warning
rather than automatically treated as a failure. If it occurred, prompt/context
provenance should be retained so reviewers can verify that Renderer A material
was never supplied.

A schema-valid declaration is therefore necessary but not sufficient to open
the A/B comparison phase.


## Current synchronization point

The active clean-room synchronization point is Contract `v0.3.0`.

The generated challenge package now contains source-grounded canonical order
context. Renderer B may implement the FHIR ServiceRequest/basedOn side from the
shared v0.3 specification, but the HL7 v2 Edition 5 order projection remains
explicitly unsupported/fail-closed until the exact machine-readable Edition 5
profile and blind external review resolve the remaining MSH-21/ORC/OBR details.

A returned declaration referencing Contract v0.2 is rejected by the scientific
readiness gate.
