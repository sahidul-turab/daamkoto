"""
Provider-agnostic LLM wrapper for DaamKoto's AI assistant.

Supported free tiers:
  - "fast"   → Groq llama-3.3-70b-versatile   (fast tool-calling, low latency)
  - "reason" → Google Gemini gemini-2.0-flash  (stronger multi-step reasoning)

Both are normalised to the same return shape:
  (text: str, tool_calls: list[ToolCall])

where ToolCall = {"name": str, "arguments": dict, "id": str}

If the "reason" model's API key is missing, it automatically falls back to "fast".
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    name: str
    arguments: dict
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")


@dataclass
class LLMResult:
    text: str
    tool_calls: list[ToolCall]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _groq_complete(
    messages: list[dict],
    tools: list[dict] | None,
    model: str,
    max_tokens: int,
    temperature: float,
) -> LLMResult:
    """Call Groq with OpenAI-compatible tool-use."""
    from groq import Groq  # lazy import — optional dep

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and add it to .env"
        )

    client = Groq(api_key=api_key)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    text = msg.content or ""
    calls: list[ToolCall] = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(name=tc.function.name, arguments=args, id=tc.id))
    return LLMResult(text=text, tool_calls=calls)


def _gemini_complete(
    messages: list[dict],
    tools: list[dict] | None,
    model: str,
    max_tokens: int,
    temperature: float,
) -> LLMResult:
    """
    Call Google Gemini via the google-genai 2.x SDK (google.genai.Client).
    Normalises Gemini's response into the same (text, tool_calls) shape.
    """
    try:
        from google import genai as google_genai  # type: ignore
        from google.genai import types as gtypes  # type: ignore
    except ImportError:
        raise ImportError(
            "google-genai is not installed. Run: pip install google-genai"
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = google_genai.Client(api_key=api_key)

    # Separate system prompt from conversation
    sys_text = ""
    gemini_contents = []

    for m in messages:
        role = m["role"]
        content = m.get("content") or ""
        if role == "system":
            sys_text = content
            continue

        if role == "tool":
            # Function result — map back to "user" turn with function_response part
            try:
                result_data = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                result_data = {"result": str(content)}
            gemini_contents.append(
                gtypes.Content(
                    role="user",
                    parts=[gtypes.Part.from_function_response(
                        name=m.get("name", "tool"),
                        response=result_data,
                    )],
                )
            )
            continue

        gemini_role = "user" if role == "user" else "model"

        if role == "assistant" and m.get("tool_calls"):
            # Assistant tool-call turn → model turn with function_call parts
            parts = []
            for tc in m["tool_calls"]:
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError, KeyError):
                    args = {}
                parts.append(gtypes.Part.from_function_call(
                    name=tc["function"]["name"],
                    args=args,
                ))
            if content:
                parts.append(gtypes.Part.from_text(text=content))
            gemini_contents.append(gtypes.Content(role="model", parts=parts))
            continue

        gemini_contents.append(
            gtypes.Content(role=gemini_role, parts=[gtypes.Part.from_text(text=content or " ")])
        )

    # Build tool declarations from OpenAI schema format
    gemini_tools = None
    if tools:
        func_decls = []
        for t in tools:
            fn = t.get("function", t)
            func_decls.append(gtypes.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters"),
            ))
        gemini_tools = [gtypes.Tool(function_declarations=func_decls)]

    cfg = gtypes.GenerateContentConfig(
        system_instruction=sys_text or None,
        max_output_tokens=max_tokens,
        temperature=temperature,
        tools=gemini_tools,
    )

    response = client.models.generate_content(
        model=model,
        contents=gemini_contents,
        config=cfg,
    )

    # Parse response
    text = ""
    calls: list[ToolCall] = []
    candidate = response.candidates[0] if response.candidates else None
    if candidate and candidate.content and candidate.content.parts:
        for part in candidate.content.parts:
            if part.text:
                text += part.text
            if part.function_call:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                args = _deep_convert(args)
                calls.append(ToolCall(name=fc.name, arguments=args))

    return LLMResult(text=text, tool_calls=calls)


def _deep_convert(obj: Any) -> Any:
    """Recursively convert Gemini proto map/list types to plain Python dicts/lists."""
    if hasattr(obj, "items"):  # MapComposite or dict
        return {k: _deep_convert(v) for k, v in obj.items()}
    if hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [_deep_convert(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Model IDs (change here if you want to swap versions)
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"

# Cache Gemini availability — once it fails auth, skip it for the process lifetime
_gemini_auth_ok: bool | None = None  # None = untested, True = works, False = auth failed


def complete(
    messages: list[dict],
    tools: list[dict] | None = None,
    model_tier: str = "fast",        # "fast" = Groq, "reason" = Gemini
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> LLMResult:
    """
    Provider-agnostic completion.

    Args:
        messages:    OpenAI-format message list (system/user/assistant/tool roles).
        tools:       OpenAI-format tool schemas (or None for plain completions).
        model_tier:  "fast" uses Groq; "reason" uses Gemini (falls back to Groq
                     if GEMINI_API_KEY is not set).
        max_tokens:  Max response tokens.
        temperature: Sampling temperature.

    Returns:
        LLMResult with .text and .tool_calls.
    """
    global _gemini_auth_ok
    if model_tier == "reason" and os.getenv("GEMINI_API_KEY") and _gemini_auth_ok is not False:
        try:
            result = _gemini_complete(messages, tools, GEMINI_MODEL, max_tokens, temperature)
            _gemini_auth_ok = True  # mark as working
            return result
        except Exception as exc:
            err_str = str(exc)
            if "401" in err_str or "UNAUTHENTICATED" in err_str or "ACCESS_TOKEN" in err_str:
                # Auth failure — disable Gemini for this process to avoid repeated retries
                _gemini_auth_ok = False
                print("[llm] Gemini auth failed — disabling for this session, using Groq only")
            else:
                print(f"[llm] Gemini failed ({exc}), falling back to Groq")

    try:
        return _groq_complete(messages, tools, GROQ_MODEL, max_tokens, temperature)
    except Exception as exc:
        err = str(exc)
        if "429" in err or "rate_limit" in err.lower() or "rate limit" in err.lower():
            raise RuntimeError(
                "The free AI quota is temporarily exhausted. "
                "Please wait a few minutes and try again, or add a GEMINI_API_KEY to .env "
                "for higher limits (get one free at https://aistudio.google.com/app/apikey)."
            ) from exc
        raise
