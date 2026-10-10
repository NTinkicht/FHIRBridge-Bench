"""Deterministic prompt assembly and post-processing for core LLM strategies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .syntax_repair import SyntaxRepairResult, repair_hl7_text_syntax

DIRECT_STRATEGY = "direct_structured_llm"
MAPPING_STRATEGY = "mapping_aware_llm"
REPAIR_STRATEGY = "mapping_aware_plus_syntax_repair"

_STRATEGIES = frozenset({DIRECT_STRATEGY, MAPPING_STRATEGY, REPAIR_STRATEGY})

DIRECT_PROMPT_PATH = Path("models/prompts/direct_structured_v0.1.txt")
MAPPING_PROMPT_PATH = Path("models/prompts/mapping_aware_v0.1.txt")


@dataclass(frozen=True)
class PreparedPrompt:
    strategy_id: str
    template_path: str
    rendered_prompt: str
    source_json: str
    mapping_context_included: bool


@dataclass(frozen=True)
class StrategyOutput:
    strategy_id: str
    raw_output: str
    final_output: str
    syntax_repair: SyntaxRepairResult | None


def _canonical_source_json(fhir_bundle: dict[str, Any]) -> str:
    if not isinstance(fhir_bundle, dict):
        raise TypeError("fhir_bundle must be an object")
    return json.dumps(
        fhir_bundle,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _load_template(path: Path, repository_root: Path) -> str:
    resolved = repository_root / path
    return resolved.read_text(encoding="utf-8")


def prepare_strategy_prompt(
    strategy_id: str,
    fhir_bundle: dict[str, Any],
    *,
    mapping_context: str | None = None,
    repository_root: Path = Path("."),
) -> PreparedPrompt:
    """Render the exact prompt for one strategy without calling a model."""

    if strategy_id not in _STRATEGIES:
        raise ValueError(f"unsupported strategy_id: {strategy_id}")

    source_json = _canonical_source_json(fhir_bundle)
    if strategy_id == DIRECT_STRATEGY:
        if mapping_context is not None:
            raise ValueError("direct strategy must not receive mapping context")
        template_path = DIRECT_PROMPT_PATH
        template = _load_template(template_path, repository_root)
        if "{{FROZEN_MAPPING_CONTEXT}}" in template:
            raise ValueError("direct prompt template leaks mapping-context slot")
        rendered = template.replace("{{FHIR_BUNDLE_JSON}}", source_json)
        mapping_included = False
    else:
        if not isinstance(mapping_context, str) or not mapping_context.strip():
            raise ValueError(
                "mapping-aware strategies require non-empty frozen mapping context"
            )
        template_path = MAPPING_PROMPT_PATH
        template = _load_template(template_path, repository_root)
        rendered = template.replace(
            "{{FROZEN_MAPPING_CONTEXT}}",
            mapping_context,
        ).replace("{{FHIR_BUNDLE_JSON}}", source_json)
        mapping_included = True

    unresolved_tokens = [
        token
        for token in ("{{FHIR_BUNDLE_JSON}}", "{{FROZEN_MAPPING_CONTEXT}}")
        if token in rendered
    ]
    if unresolved_tokens:
        raise ValueError(
            "prompt template contains unresolved token(s): "
            + ", ".join(unresolved_tokens)
        )

    return PreparedPrompt(
        strategy_id=strategy_id,
        template_path=str(template_path),
        rendered_prompt=rendered,
        source_json=source_json,
        mapping_context_included=mapping_included,
    )


def process_strategy_output(
    strategy_id: str,
    raw_output: str,
) -> StrategyOutput:
    """Apply only the post-processing permitted for the selected strategy."""

    if strategy_id not in _STRATEGIES:
        raise ValueError(f"unsupported strategy_id: {strategy_id}")
    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string")

    if strategy_id != REPAIR_STRATEGY:
        return StrategyOutput(
            strategy_id=strategy_id,
            raw_output=raw_output,
            final_output=raw_output,
            syntax_repair=None,
        )

    repair = repair_hl7_text_syntax(raw_output)
    return StrategyOutput(
        strategy_id=strategy_id,
        raw_output=raw_output,
        final_output=repair.output,
        syntax_repair=repair,
    )
