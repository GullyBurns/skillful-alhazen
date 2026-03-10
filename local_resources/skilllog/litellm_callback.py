#!/usr/bin/env python3
"""
LiteLLM CustomLogger for OpenClaw token usage tracking.

Fires after every LLM API call that passes through the LiteLLM proxy.
Posts token counts to the alhazen-mcp HTTP endpoint, which writes to TypeDB.

No external dependencies — uses only Python stdlib (urllib.request) so this
file can be mounted into the read-only LiteLLM container without pip installs.

Configuration (via env vars in litellm container):
    MCP_LOG_URL   — URL of the MCP /log-llm-call endpoint
                    (default: http://alhazen-mcp:3000/log-llm-call)

Wired via litellm-config.yaml:
    litellm_settings:
      callbacks: ["litellm_callback.proxy_handler_instance"]
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:
    # Allow importing outside the LiteLLM container for local testing
    class CustomLogger:  # type: ignore[no-redef]
        pass

# ---------------------------------------------------------------------------
# Monkey-patch litellm.acompletion to strip web_search_options globally.
#
# LiteLLM's Anthropic pass-through adapter converts Anthropic web_search
# tools into web_search_options in completion_kwargs, then calls
# litellm.acompletion(**completion_kwargs). Most providers (Groq/qwen3-32b,
# Anthropic, Ollama) reject or ignore this param. Stripping it here is safe
# because OpenClaw uses its own SearXNG for web search, not the LLM API.
# ---------------------------------------------------------------------------
try:
    import litellm as _litellm
    _orig_acompletion = _litellm.acompletion

    async def _acompletion_drop_web_search(*args, **kwargs):
        kwargs.pop("web_search_options", None)
        return await _orig_acompletion(*args, **kwargs)

    _litellm.acompletion = _acompletion_drop_web_search
except Exception as _patch_err:
    print(f"[skilllog-litellm] WARNING: could not patch acompletion: {_patch_err}",
          file=sys.stderr)

# ---------------------------------------------------------------------------
# Pricing (USD per token) — claude-sonnet-4-6 rates
# Update these if model pricing changes.
# ---------------------------------------------------------------------------
_RATES: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input":         3.00 / 1_000_000,
        "output":       15.00 / 1_000_000,
        "cache_create":  3.75 / 1_000_000,
        "cache_read":    0.30 / 1_000_000,
    },
    "claude-opus-4-6": {
        "input":        15.00 / 1_000_000,
        "output":       75.00 / 1_000_000,
        "cache_create": 18.75 / 1_000_000,
        "cache_read":    1.50 / 1_000_000,
    },
    "claude-haiku-4-5-20251001": {
        "input":         0.80 / 1_000_000,
        "output":        4.00 / 1_000_000,
        "cache_create":  1.00 / 1_000_000,
        "cache_read":    0.08 / 1_000_000,
    },
}
_ZERO_RATES = {
    "input":        0.0,
    "output":       0.0,
    "cache_create": 0.0,
    "cache_read":   0.0,
}


def _compute_cost(model: str, input_tok: int, output_tok: int,
                  cache_create: int, cache_read: int) -> float:
    """Calculate cost in USD from Anthropic token counts (not LiteLLM's calculator)."""
    # Normalise model name — LiteLLM may prefix with provider name
    clean = model.replace("anthropic/", "").replace("openai/", "").replace("ollama/", "")
    # Local inference (Ollama) and any unrecognised model defaults to zero cost
    rates = _RATES.get(clean, _ZERO_RATES)
    return (
        input_tok    * rates["input"]
        + output_tok * rates["output"]
        + cache_create * rates["cache_create"]
        + cache_read   * rates["cache_read"]
    )


class TypeDBTokenLogger(CustomLogger):
    """
    Posts each successful/failed LLM call to the alhazen-mcp /log-llm-call
    endpoint (stdlib HTTP only — no typedb-driver needed here).
    """

    def __init__(self):
        super().__init__()
        self._mcp_url = os.environ.get(
            "MCP_LOG_URL", "http://localhost:3000/log-llm-call"
        )

    # ------------------------------------------------------------------
    # LiteLLM callback entry points
    # ------------------------------------------------------------------

    async def async_pre_call_hook(self, user_api_key_dict: Any,
                                   cache: Any, data: dict,
                                   call_type: str) -> dict:
        """Strip web search tools/params before forwarding to providers.

        LiteLLM's Anthropic pass-through adapter converts Anthropic web_search
        tools (type: 'web_search_20250305') into web_search_options in the
        completion kwargs. Many providers and models don't support this.
        Strip the tool here so the adapter never generates web_search_options.
        """
        # Strip Anthropic-format web_search tools from the tools array.
        tools = data.get("tools")
        if isinstance(tools, list):
            filtered = [
                t for t in tools
                if not (isinstance(t, dict)
                        and "web_search" in t.get("type", "").lower())
            ]
            if filtered:
                data["tools"] = filtered
            else:
                data.pop("tools", None)
        # Also strip if web_search_options somehow arrives at the top level.
        data.pop("web_search_options", None)
        return data

    def log_success_event(self, kwargs: Any, response_obj: Any,
                          start_time: Any, end_time: Any) -> None:
        self._post(kwargs, response_obj, start_time, end_time, success=True)

    async def async_log_success_event(self, kwargs: Any, response_obj: Any,
                                      start_time: Any, end_time: Any) -> None:
        self._post(kwargs, response_obj, start_time, end_time, success=True)

    async def async_log_failure_event(self, kwargs: Any, response_obj: Any,
                                      start_time: Any, end_time: Any) -> None:
        self._post(kwargs, response_obj, start_time, end_time, success=False)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _post(self, kwargs: Any, response_obj: Any,
              start_time: Any, end_time: Any, success: bool) -> None:
        try:
            usage = getattr(response_obj, "usage", None)
            if not usage:
                return

            # Extract token counts directly from response object.
            # LiteLLM's own cost calculations for cache tokens are buggy
            # (issues #7790, #11364) — we calculate manually.
            input_tok    = getattr(usage, "prompt_tokens", 0) or 0
            output_tok   = getattr(usage, "completion_tokens", 0) or 0
            cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read   = getattr(usage, "cache_read_input_tokens", 0) or 0
            try:
                elapsed = end_time - start_time
                if hasattr(elapsed, "total_seconds"):
                    duration_ms = int(elapsed.total_seconds() * 1000)
                else:
                    duration_ms = int(elapsed * 1000)
            except Exception:
                duration_ms = 0
            model        = kwargs.get("model", "unknown")

            # Session ID — populated if OpenClaw passes it in metadata (Phase 2)
            session_id = (
                kwargs.get("litellm_params", {})
                      .get("metadata", {})
                      .get("session_id", "unknown")
            )

            cost = _compute_cost(model, input_tok, output_tok,
                                 cache_create, cache_read)

            payload = {
                "model":          model,
                "session_id":     session_id,
                "input_tokens":   input_tok,
                "output_tokens":  output_tok,
                "cache_creation_tokens": cache_create,
                "cache_read_tokens":     cache_read,
                "cost_usd":       cost,
                "duration_ms":    duration_ms,
                "success":        success,
            }

            body = json.dumps(payload).encode()
            req  = urllib.request.Request(
                self._mcp_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)

        except Exception as exc:
            # Never let a logging failure break the LLM request flow.
            print(f"[skilllog-litellm] WARNING: failed to log call: {exc}",
                  file=sys.stderr)


# Instance referenced in litellm_settings.callbacks
proxy_handler_instance = TypeDBTokenLogger()
