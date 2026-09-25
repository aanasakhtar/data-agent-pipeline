"""
engine/semantic_resolver.py
=============================
The actual L4/L5 semantic resolution step: turns a customer's free-text
goal into a MetricContract, choosing physical gold-layer tables/columns
from a supplied semantic model description, and setting
`resolution_status` correctly (RESOLVED / RESOLVED_WITH_ASSUMPTION /
AMBIGUOUS_NEEDS_INPUT / NOT_MEASURABLE / UNSUPPORTED_BY_AVAILABLE_DATA)
rather than always assuming success.

Supports both OpenAI (default when OPENAI_API_KEY is present, aligned
with Claimb Command Center MVP2) and Anthropic (when ANTHROPIC_API_KEY
is set), with full testability via injected fake clients.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple

from dotenv import load_dotenv
from pydantic import ValidationError

from engine.schemas import MetricContract

# Load local .env if present (e.g. from repo root)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def get_resolver_config() -> Tuple[str, str]:
    """Returns (provider, model) detected from environment or configuration."""
    provider = os.environ.get("CLAIMB_RESOLVER_PROVIDER")
    if not provider:
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            provider = "openai"

    model = os.environ.get("CLAIMB_RESOLVER_MODEL")
    if not model:
        if provider == "openai":
            model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        else:
            model = "claude-sonnet-5"
    return provider, model


DEFAULT_PROVIDER, DEFAULT_MODEL = get_resolver_config()

# Fields the LLM is asked to produce. Deliberately excludes fields the
# CALLER supplies (metric_id, version, business_process, provenance,
# semantic_model_ref, verified_query_ref) -- those are pipeline
# bookkeeping, not semantic understanding, and asking the model to
# invent them would just be one more thing that could hallucinate for
# no benefit.
_LLM_OWNED_FIELDS = (
    "metric_name",
    "user_goal_text",
    "semantic_definition",
    "direction",
    "numerator_definition",
    "denominator_definition",
    "grain",
    "unit",
    "time_window",
    "inclusion_rules",
    "exclusion_rules",
    "dimensions",
    "target_value",
    "target_source",
    "source_entities",
    "gold_fields",
    "executable_query_template",
    "expected_result_shape",
    "data_quality_requirements",
    "minimum_sample_guidance",
    "resolution_status",
    "resolution_notes",
)


class SemanticResolutionError(Exception):
    """Raised for operational failures: the model's response wasn't
    valid JSON, or the JSON didn't validate as the LLM-owned subset of
    MetricContract's fields at all. A legitimate AMBIGUOUS_NEEDS_INPUT
    or NOT_MEASURABLE resolution from the model is NOT this -- that's a
    successfully resolved MetricContract whose resolution_status happens
    to block progress, not an error."""


class MessagesLike(Protocol):
    """Structural type for clients with a create(...) method."""

    def create(self, **kwargs: Any) -> Any: ...


def _get_default_client(provider: Optional[str] = None) -> Any:
    prov, _ = get_resolver_config()
    target_provider = provider or prov

    if target_provider == "openai":
        try:
            import openai
        except ImportError as exc:
            raise SemanticResolutionError(
                "the 'openai' package is not installed -- run `pip install openai` "
                "(it's in engine/requirements.txt) or pass an explicit `client` argument"
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SemanticResolutionError(
                "OPENAI_API_KEY is not set -- semantic resolution requires a "
                "live model call. Set the environment variable in .env, or pass an "
                "explicit `client` argument (e.g. a fake client in tests)."
            )
        return openai.OpenAI(api_key=api_key)

    elif target_provider == "anthropic":
        try:
            import anthropic
        except ImportError as exc:
            raise SemanticResolutionError(
                "the 'anthropic' package is not installed -- run `pip install anthropic` "
                "(it's in engine/requirements.txt) or pass an explicit `client` argument"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise SemanticResolutionError(
                "ANTHROPIC_API_KEY is not set -- semantic resolution requires a "
                "live model call. Set the environment variable, or pass an "
                "explicit `client` argument (e.g. a fake client in tests)."
            )
        return anthropic.Anthropic(api_key=api_key)

    else:
        raise SemanticResolutionError(f"Unsupported resolver provider: {target_provider}")


def build_resolver_prompt(
    customer_input_text: str, semantic_model: Dict[str, Any], business_function: str
) -> str:
    """
    Pure function, fully unit-testable without any network access.
    `semantic_model` describes the gold-layer tables/columns available
    to query against -- e.g.:

        {
          "gold.fct_orders": ["order_id", "customer_id", "order_status", ...],
          "gold.fct_support_tickets": ["ticket_id", "order_id", ...],
          "gold.dim_customers": ["customer_id", "plan_tier", ...]
        }
    """
    schema_description = json.dumps(semantic_model, indent=2)
    fields_description = ", ".join(_LLM_OWNED_FIELDS)

    return f"""You are the metric-resolution layer of an enterprise data agent. A customer has \
described a business goal in their own words. Your job is to translate that \
into a precise, machine-executable metric definition against the customer's \
OWN gold-layer warehouse schema -- and to be honest when you cannot.

Business function: {business_function}

Customer's stated goal (verbatim, do not paraphrase away ambiguity):
\"\"\"{customer_input_text}\"\"\"

Available gold-layer tables and columns (this is the ONLY data you may \
reference -- never invent a table or column name that isn't listed here):
{schema_description}

Respond with ONLY a single valid JSON object (no markdown fences, no commentary \
before or after) with exactly these keys: {fields_description}.

STRICT RESOLUTION STATUS CRITERIA (Evaluate in this exact order):
1. UNSUPPORTED_BY_AVAILABLE_DATA:
   If the goal references entities, events, or metrics not present in the schema (e.g. 'onboarding experience score', 'churn', 'NPS', 'employee happiness'), set resolution_status to 'UNSUPPORTED_BY_AVAILABLE_DATA'. Do NOT substitute a different metric (e.g., do not use CSAT or support tickets as a proxy for onboarding or churn). Explain the missing data in resolution_notes.
2. AMBIGUOUS_NEEDS_INPUT:
   Only set if the goal is truly non-specific and lacks any clear operational concept (e.g. 'make things better', 'faster operations', 'improve satisfaction' without naming which process or event). If the customer names a specific operational process and condition (e.g. 'straight-through order completion (no ticket needed)'), that is NOT ambiguous -- resolve it against the schema even if no numerical target is specified (target_value should be null).
3. RESOLVED or RESOLVED_WITH_ASSUMPTION:
   When the goal names a clear process and condition that maps to specific tables and columns in the available schema.

STRICT FIELD TYPES:
- 'inclusion_rules', 'exclusion_rules', 'dimensions', 'source_entities', 'gold_fields', 'data_quality_requirements' MUST be JSON arrays of strings (e.g. ["rule1"]).
- 'expected_result_shape' MUST be a string describing the output columns (e.g. "single row: completed_orders (int), straight_through_rate (float)").

RULES FOR UNRESOLVED STATUSES (AMBIGUOUS_NEEDS_INPUT, UNSUPPORTED_BY_AVAILABLE_DATA, NOT_MEASURABLE):
- If resolution_status is NOT 'RESOLVED' and NOT 'RESOLVED_WITH_ASSUMPTION':
  * 'executable_query_template' MUST be an empty string '' (DO NOT write any SQL query).
  * 'metric_name' MUST be empty string ''.
  * 'numerator_definition' and 'denominator_definition' MUST be empty strings ''.
  * 'source_entities' and 'gold_fields' MUST be empty lists [].
  * 'inclusion_rules' and 'exclusion_rules' MUST be empty lists [].
  * 'dimensions' and 'data_quality_requirements' MUST be empty lists [].
  * 'direction' MUST be 'higher_is_better'.
  * 'target_value' MUST be null.

RULES FOR RESOLVED STATUSES:
- 'source_entities' MUST contain the EXACT full table names from the schema above (e.g. 'gold.fct_orders', 'gold.fct_support_tickets'), NEVER shortened or informal names like 'orders'.
- 'gold_fields' MUST contain exact 'table.column' names.
- 'direction' MUST be either 'higher_is_better' or 'lower_is_better'.
- 'numerator_definition' and 'denominator_definition' MUST both be defined and non-empty.
- 'executable_query_template' MUST be valid DuckDB SQL referencing ONLY tables/columns from the schema above, and must return a single row whose LAST column is the metric's own value (a rate, a count, or similar).
- 'target_value' MUST be a float if stated by customer (e.g. 0.90 for 90%), or null if not stated -- never invent a target the customer didn't give you.
- 'dimensions' MUST list entity attributes from the schema the metric can be segmented by (e.g. ['plan_tier']). If the customer mentions segments or breakdown dimensions in their goal (e.g. 'plan tiers'), you MUST include that attribute (e.g. 'plan_tier').

Respond with the JSON object now."""


def parse_llm_json_response(raw_text: str) -> Dict[str, Any]:
    """
    Strips markdown code fences if present and parses JSON.
    Raises SemanticResolutionError with original text included on failure.
    """
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n(.*)\n```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SemanticResolutionError(
            f"model response was not valid JSON ({exc}). Raw response: {raw_text[:500]!r}"
        ) from exc


def normalize_llm_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes minor formatting variances from LLMs (e.g. string where list expected)
    into strict Pydantic-compatible shapes.
    """
    payload = dict(parsed)
    list_fields = (
        "inclusion_rules",
        "exclusion_rules",
        "dimensions",
        "source_entities",
        "gold_fields",
        "data_quality_requirements",
    )
    for f in list_fields:
        if f in payload:
            val = payload[f]
            if isinstance(val, str):
                payload[f] = [val] if val.strip() else []
            elif not isinstance(val, list):
                payload[f] = [str(val)] if val is not None else []

    str_fields = (
        "metric_name",
        "user_goal_text",
        "semantic_definition",
        "numerator_definition",
        "denominator_definition",
        "grain",
        "unit",
        "time_window",
        "target_source",
        "executable_query_template",
        "expected_result_shape",
        "minimum_sample_guidance",
        "resolution_notes",
    )
    for f in str_fields:
        if f in payload:
            val = payload[f]
            if isinstance(val, list):
                payload[f] = "; ".join(str(x) for x in val)
            elif isinstance(val, dict):
                payload[f] = json.dumps(val)
            elif val is None and f in (
                "metric_name",
                "user_goal_text",
                "semantic_definition",
                "numerator_definition",
                "denominator_definition",
                "grain",
                "unit",
                "time_window",
                "executable_query_template",
                "expected_result_shape",
            ):
                payload[f] = ""

    if payload.get("target_source") is None:
        payload["target_source"] = "not specified by customer"
    if payload.get("minimum_sample_guidance") is None:
        payload["minimum_sample_guidance"] = "not specified"

    # Ensure unresolved statuses have valid defaults while preserving any sneaky queries for evaluation
    if payload.get("resolution_status") not in ("RESOLVED", "RESOLVED_WITH_ASSUMPTION"):
        if payload.get("executable_query_template") is None:
            payload["executable_query_template"] = ""
        if payload.get("direction") not in ("higher_is_better", "lower_is_better"):
            payload["direction"] = "higher_is_better"

    return payload


def _dispatch_model_call(
    client: Any,
    prompt: str,
    model: str,
    max_tokens: int,
) -> str:
    """Dispatches prompt to OpenAI, Anthropic, or an injected test fake."""
    # 1. Real OpenAI client (has .chat.completions.create)
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    # 2. Real Anthropic client (has .messages.create)
    if hasattr(client, "messages") and hasattr(client.messages, "create"):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # 3. Direct create method (FakeAnthropicMessages in tests, or passed client.messages)
    if hasattr(client, "create"):
        try:
            response = client.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except TypeError:
            response = client.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

        if hasattr(response, "content") and response.content:
            return response.content[0].text
        elif hasattr(response, "choices") and response.choices:
            return response.choices[0].message.content or ""
        elif isinstance(response, str):
            return response
        else:
            raise SemanticResolutionError(
                f"unexpected response shape from client.create(...): {response!r}"
            )

    raise SemanticResolutionError(f"unrecognized client type: {type(client)}")


def resolve_metric_contract(
    *,
    customer_input_text: str,
    semantic_model: Dict[str, Any],
    business_function: str,
    metric_id: str,
    version: int = 1,
    client: Optional[Any] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2000,
) -> MetricContract:
    """
    The live L4/L5 step. Builds the prompt, calls the model (or the
    injected fake), parses and validates the response, and constructs a
    full MetricContract by merging the LLM-owned fields with the
    caller-supplied bookkeeping fields.
    """
    active_provider, default_model = get_resolver_config()
    target_provider = provider or active_provider
    target_model = model or default_model

    prompt = build_resolver_prompt(customer_input_text, semantic_model, business_function)

    active_client = client or _get_default_client(target_provider)
    raw_text = _dispatch_model_call(
        client=active_client,
        prompt=prompt,
        model=target_model,
        max_tokens=max_tokens,
    )

    parsed = parse_llm_json_response(raw_text)

    unknown_fields = set(parsed.keys()) - set(_LLM_OWNED_FIELDS)
    if unknown_fields:
        raise SemanticResolutionError(
            f"model response included fields it was not asked for: {unknown_fields} "
            "-- refusing to silently accept unrequested content in a contract"
        )
    missing_fields = set(_LLM_OWNED_FIELDS) - set(parsed.keys())
    if missing_fields:
        raise SemanticResolutionError(
            f"model response is missing required fields: {missing_fields}"
        )

    # Normalize minor formatting quirks (e.g. lists vs strings) before Pydantic validation
    normalized = normalize_llm_payload(parsed)

    contract_payload = dict(normalized)
    contract_payload.update(
        {
            "metric_id": metric_id,
            "version": version,
            "business_process": business_function,
            "provenance": f"resolved by engine.semantic_resolver via provider={target_provider} model={target_model}",
            "semantic_model_ref": None,
            "verified_query_ref": None,
        }
    )

    try:
        return MetricContract.model_validate(contract_payload)
    except ValidationError as exc:
        raise SemanticResolutionError(
            f"model's response did not validate as a MetricContract: {exc}"
        ) from exc
