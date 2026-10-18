"""Synthetic only: exercise the executable clean-room identity gate, never source rules."""
from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import yaml

from renderer_validation.validate_renderer_b_declaration import ROOT, assess, canonical_sha


class IsolatedHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.challenge = self.root / "challenge"
        (self.challenge / "inputs").mkdir(parents=True)
        cases = []
        for n in range(1, 13):
            case_id = f"RB-{n:03d}"
            graph = {
                "graph_id": f"SYNTHETIC-HANDOFF-TEST-{n}",
                "scenario_metadata": {
                    "partition": "development", "synthetic_only": True
                },
                "facts": [],
            }
            (self.challenge / "inputs" / f"{case_id}.json").write_text(
                json.dumps(graph), encoding="utf-8"
            )
            cases.append({
                "case_id": case_id, "scenario_id": f"LAB-{n:03d}",
                "input_path": f"inputs/{case_id}.json",
                "graph_sha256": canonical_sha(graph),
                "primary_endpoint_eligible": n != 12,
                "contract_state": "INDETERMINATE" if n == 12 else "SCORABLE",
            })
        manifest = {
            "challenge_id": "FHIRBRIDGE-RENDERER-B-DEV-001",
            "version": "0.3.0", "partition": "development",
            "contract": {"version": "0.3.0"},
            "contains_renderer_a_output": False,
            "contains_target_gold_serialization": False,
            "contains_verifier_decisions": False,
            "contains_fault_labels": False,
            "cases": cases,
        }
        manifest["manifest_sha256"] = canonical_sha(manifest)
        (self.challenge / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        contract_bytes = (ROOT / "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml").read_bytes()
        info = {
            "repository_full_name": "NTinkicht/FHIRBridge-Bench",
            "branch": "renderer-b-cleanroom",
            "starting_commit": "a" * 40,  # synthetic TEST identity, not real custody
            "challenge_id": "FHIRBRIDGE-RENDERER-B-DEV-001",
            "challenge_version": "0.3.0",
            "challenge_manifest_sha256": manifest["manifest_sha256"],
            "contract_path": "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml",
            "contract_sha256": sha256(contract_bytes).hexdigest(),
        }
        expected = {
            "schema_version": "0.1.0",
            "handoff_id": "FHIRBRIDGE-RENDERER-B-HANDOFF-TEST",
            "created_at": "2026-10-18T01:00:00Z",
            "clean_room_inputs": info,
        }
        declaration = yaml.safe_load(
            (ROOT / "renderer_validation/examples/renderer_b_declaration_template.yaml").read_text(encoding="utf-8")
        )
        declaration["renderer_id"] = "RENDERER-B-TEST"
        declaration["contributor"]["identity"] = "CODEX-SYNTHETIC-TEST"
        declaration["implementation"]["language"] = "Java 17"
        declaration["implementation"]["source_commit"] = "b" * 40
        declaration["implementation_period"]["started_on"] = "2026-10-18"
        declaration["implementation_period"]["completed_on"] = "2026-10-18"
        declaration["independence"]["declaration_complete"] = True
        declaration["known_unsupported_cases"] = ["Order projection remains unsupported"]
        declaration["clean_room_inputs"] = deepcopy(info)
        self.expected = expected
        self.declaration = declaration

    def assess_current(self):
        decl = self.root / "declaration.yaml"
        inputs = self.root / "expected.yaml"
        decl.write_text(yaml.safe_dump(self.declaration), encoding="utf-8")
        inputs.write_text(yaml.safe_dump(self.expected), encoding="utf-8")
        return assess(decl, inputs, self.challenge)

    def test_positive_exploratory_only_real_instance_identity(self):
        result = self.assess_current()
        self.assertTrue(result["ready_for_exploratory_agent_comparison"], result["blockers"])
        self.assertFalse(result["ready_for_differential_comparison"])
        self.assertFalse(result["confirmatory_permission"])

    def test_custodian_starting_commit_mismatch_fails(self):
        self.expected["clean_room_inputs"]["starting_commit"] = "c" * 40
        self.assertFalse(self.assess_current()["ready_for_exploratory_agent_comparison"])

    def test_contract_byte_mismatch_on_both_records_fails(self):
        self.expected["clean_room_inputs"]["contract_sha256"] = "e" * 64
        self.declaration["clean_room_inputs"]["contract_sha256"] = "e" * 64
        self.assertFalse(self.assess_current()["ready_for_exploratory_agent_comparison"])

    def test_graph_tamper_and_oracle_hint_fail(self):
        case = self.challenge / "inputs" / "RB-001.json"
        graph = json.loads(case.read_text(encoding="utf-8"))
        graph["verifierVerdict"] = "PASS"
        graph["assertions"] = [{"expected_value": "oracle"}]
        case.write_text(json.dumps(graph), encoding="utf-8")
        result = self.assess_current()
        self.assertFalse(result["ready_for_exploratory_agent_comparison"])
        self.assertTrue(any("prohibited" in x for x in result["blockers"]))
        self.assertTrue(any("hash" in x for x in result["blockers"]))

    def _relock_after_mutation(self, case_id="RB-001"):
        # Deliberately forge *matching* internal hashes to test semantic checks.
        file = self.challenge / "inputs" / f"{case_id}.json"
        graph = json.loads(file.read_text(encoding="utf-8"))
        manifest_path = self.challenge / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            if case["case_id"] == case_id:
                case["graph_sha256"] = canonical_sha(graph)
        manifest["manifest_sha256"] = canonical_sha({
            k: v for k, v in manifest.items() if k != "manifest_sha256"
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.expected["clean_room_inputs"]["challenge_manifest_sha256"] = manifest["manifest_sha256"]
        self.declaration["clean_room_inputs"]["challenge_manifest_sha256"] = manifest["manifest_sha256"]

    def test_compound_sensitive_namespaces_fail_even_when_all_hashes_are_relocked(self):
        for field in (
            "semanticVerifierClassification",
            "seededFaultLabel",
            "sourceRendererAOutput",
        ):
            with self.subTest(field=field):
                case = self.challenge / "inputs" / "RB-001.json"
                original = json.loads(case.read_text(encoding="utf-8"))
                changed = deepcopy(original)
                changed["facts"].append({field: "sensitive-synthetic-sentinel"})
                case.write_text(json.dumps(changed), encoding="utf-8")
                self._relock_after_mutation()
                result = self.assess_current()
                self.assertFalse(result["ready_for_exploratory_agent_comparison"])
                self.assertTrue(
                    any("prohibited reference/output field" in x for x in result["blockers"]),
                    result["blockers"],
                )
                case.write_text(json.dumps(original), encoding="utf-8")
                self._relock_after_mutation()

    def test_benign_substrings_remain_permitted_after_full_rehash(self):
        for field in ("default", "default_unit", "unexpected_status"):
            with self.subTest(field=field):
                case = self.challenge / "inputs" / "RB-001.json"
                original = json.loads(case.read_text(encoding="utf-8"))
                changed = deepcopy(original)
                changed["facts"].append({field: "SYNTHETIC BENIGN VALUE"})
                case.write_text(json.dumps(changed), encoding="utf-8")
                self._relock_after_mutation()
                result = self.assess_current()
                self.assertTrue(
                    result["ready_for_exploratory_agent_comparison"],
                    result["blockers"],
                )
                case.write_text(json.dumps(original), encoding="utf-8")
                self._relock_after_mutation()

    def test_forged_manifest_and_custodian_challenge_id_fails(self):
        path = self.challenge / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["challenge_id"] = "UNRELATED-SYNTHETIC-CHALLENGE"
        manifest["manifest_sha256"] = canonical_sha({
            k: v for k, v in manifest.items() if k != "manifest_sha256"
        })
        path.write_text(json.dumps(manifest), encoding="utf-8")
        for record in (self.expected["clean_room_inputs"], self.declaration["clean_room_inputs"]):
            record["challenge_id"] = "UNRELATED-SYNTHETIC-CHALLENGE"
            record["challenge_manifest_sha256"] = manifest["manifest_sha256"]
        result = self.assess_current()
        self.assertFalse(result["ready_for_exploratory_agent_comparison"])
        self.assertTrue(any("manifest ID" in x for x in result["blockers"]))

    def test_legitimate_reference_range_field_is_not_banned(self):
        case = self.challenge / "inputs" / "RB-001.json"
        graph = json.loads(case.read_text(encoding="utf-8"))
        graph["facts"].append({"reference_range": {"low": "1", "high": "5"}})
        case.write_text(json.dumps(graph), encoding="utf-8")
        self._relock_after_mutation()
        result = self.assess_current()
        self.assertTrue(result["ready_for_exploratory_agent_comparison"], result["blockers"])

    def test_codex_authorship_false_blocks(self):
        self.declaration["independence"]["llm_generated_mapping_code_used"] = False
        self.assertFalse(self.assess_current()["ready_for_exploratory_agent_comparison"])

    def test_metadata_version_mismatch_blocks(self):
        path = self.challenge / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["version"] = "0.2.0"
        manifest["manifest_sha256"] = canonical_sha({k: v for k, v in manifest.items() if k != "manifest_sha256"})
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertFalse(self.assess_current()["ready_for_exploratory_agent_comparison"])


if __name__ == "__main__":
    unittest.main()
