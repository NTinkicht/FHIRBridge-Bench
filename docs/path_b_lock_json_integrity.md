# Path B — unambiguous private response-lock JSON

The original blind Edition 5 extraction response is stored as immutable
first-round YAML bytes. Its coordinator-generated lock is a separate JSON
document recording hashes and readiness. Two CLI entry points later read
that lock:

- `qualification/hl7v2/required_element_review/lock_responses.py compare`
- `qualification/hl7v2/required_element_review/build_adjudication_handoff.py`

They now share `fhirbridge.lri_lock_json.load_coordinator_lock_json`.
It rejects duplicate JSON keys **at any nesting level**, non-JSON numeric
constants (NaN and infinities), malformed UTF-8, non-object roots and
oversized files. This prevents contradictory source hashes and qualifications
from being interpreted differently by human and software consumers.

Parsing a lock is only an input hygiene step. The subsequent
`verify_response_lock` still checks the **entire** lock against a newly
computed record from the original, unchanged reviewer submission bytes.
Even a consistent first-round hash is not a digital signature or proof of
human identity, independence, normative completeness, conformance or
clinical validity.

Keep actual response and lock bytes in approved private custody and never
write them into public CI/GitHub. No reviewer appointment, G1-qualified
conformance, confirmatory permission or scientific freeze is asserted here.
