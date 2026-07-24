"""
DaamKoto AI Agent — autonomous PC advisor.

Replaces the old single-shot chatbot.translate_to_params() pattern with a
real agentic loop that can chain up to MAX_ITERS tool calls before giving
a final answer.

Architecture:
  run(message, history, context, conn)
    → LLMResult (text + tool_calls) via llm.complete()
    → if tool_calls: execute via tools.execute_tool(), append results, repeat
    → synthesise final response into { text, blocks[], actions[] }

Routing:
  Simple single-tool queries → model_tier="fast" (Groq, low latency, free)
  Build planning / compatibility / multi-step → model_tier="reason" (Gemini, free)
"""

from __future__ import annotations

import json
from typing import Any

from backend import database, llm, tools

MAX_ITERS = 4  # Hard cap on agent loop iterations (protects free-tier quota)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are DaamKoto, Bangladesh's PC parts advisor. Find prices, plan builds, check compatibility, track deals across 13 retailers.

CRITICAL RULES (follow exactly):
1. NEVER answer from memory. ALWAYS call a tool before responding.
2. Budget question (e.g. "70000 taka PC") → call plan_build(budget_bdt=70000, use_case="gaming").
3. Product search → call search_products with the right category and filters.
4. Price trend → call get_price_history(product_id=...).
5. After tool result, respond in 2-3 sentences. Do NOT make up data.
6. Taka shortcuts: "70k"=70000, "৳5000"=5000, "5k taka"=5000.

Categories: RAM DESKTOP, RAM LAPTOP, GPU, PROCESSOR, MOTHERBOARD, SSD, PORTABLE SSD, HDD, PORTABLE HDD, PSU, CPU COOLER, CASING COOLER, CASING.

Optionally emit UI actions at the very end:
<actions>[{"type":"open_deals"}]</actions>"""

# ---------------------------------------------------------------------------
# Routing heuristic: decide which model tier to use
# ---------------------------------------------------------------------------

_REASON_KEYWORDS = {
    "build", "plan", "budget", "compatible", "compatibility", "fit", "check",
    "history", "trend", "compare", "vs", "versus", "difference", "recommend",
    "upgrade", "bottleneck", "taka theke", "takar modhye",
}


def _needs_reason_model(message: str, history: list[dict]) -> bool:
    """Return True if the query warrants the 'reason' (Gemini) model."""
    text = message.lower()
    if any(kw in text for kw in _REASON_KEYWORDS):
        return True
    # Multi-turn conversations with tool results benefit from stronger context
    tool_turns = sum(1 for m in history if m.get("role") == "tool")
    return tool_turns >= 2


# ---------------------------------------------------------------------------
# Block extraction helpers
# ---------------------------------------------------------------------------

def _make_product_list_block(tool_result: dict, title: str = "Products found") -> dict:
    products = tool_result.get("products", [])
    return {
        "type": "product_list",
        "title": title,
        "total": tool_result.get("total", len(products)),
        "products": products,
    }


def _make_build_sheet_block(tool_result: dict) -> dict:
    return {
        "type": "build_sheet",
        "profile": tool_result.get("profile", "balanced"),
        "budget_bdt": tool_result.get("budget_bdt"),
        "total_cost": tool_result.get("total_cost"),
        "within_budget": tool_result.get("within_budget", True),
        "slots": tool_result.get("slots", []),
        "compatibility": tool_result.get("compatibility", {}),
    }


def _make_price_history_block(tool_result: dict) -> dict:
    return {
        "type": "price_history",
        "product_id": tool_result.get("product_id"),
        "current_price": tool_result.get("current_price"),
        "all_time_low": tool_result.get("all_time_low"),
        "all_time_high": tool_result.get("all_time_high"),
        "trend": tool_result.get("trend", "stable"),
        "history": tool_result.get("history", []),
    }


def _make_compat_report_block(tool_result: dict) -> dict:
    return {
        "type": "compat_report",
        "issues": tool_result.get("issues", []),
        "estimated_watts": tool_result.get("estimated_watts"),
        "recommended_psu": tool_result.get("recommended_psu"),
        "has_errors": tool_result.get("has_errors", False),
    }


def _make_deal_list_block(tool_result: dict) -> dict:
    return {
        "type": "deal_list",
        "deals": tool_result.get("deals", []),
        "count": tool_result.get("count", 0),
    }


def _make_product_detail_block(tool_result: dict) -> dict:
    return {
        "type": "product_detail",
        "product": tool_result,
    }


_BLOCK_FACTORIES = {
    "search_products":     _make_product_list_block,
    "get_product_details": _make_product_detail_block,
    "get_price_history":   _make_price_history_block,
    "check_compatibility": _make_compat_report_block,
    "plan_build":          _make_build_sheet_block,
    "get_deals":           _make_deal_list_block,
}


# ---------------------------------------------------------------------------
# Action extraction from agent text
# ---------------------------------------------------------------------------

def _extract_actions(text: str) -> tuple[str, list[dict]]:
    """
    Pull the <actions>[...]</actions> block out of the agent's final text.
    Returns (cleaned_text, actions_list).
    """
    import re
    pattern = r"<actions>\s*(\[.*?\])\s*</actions>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return text, []
    try:
        actions = json.loads(match.group(1))
    except json.JSONDecodeError:
        actions = []
    cleaned = text[: match.start()].rstrip() + text[match.end():]
    return cleaned.strip(), actions


# ---------------------------------------------------------------------------
# Token-saving: summarise large tool results before sending back to the LLM
# ---------------------------------------------------------------------------

def _summarize_for_llm(tool_name: str, result: dict) -> str:
    """
    Return a compact summary of a tool result for the LLM message history.
    The full result is stored in blocks for the UI; the LLM only needs the key facts.
    This keeps Groq free-tier token usage low.
    """
    if result.get("error"):
        return f"Error: {result['error']}"

    if tool_name == "search_products":
        products = result.get("products", [])
        total = result.get("total", len(products))
        if not products:
            return f"No products found (total=0)."
        lines = [f"Found {total} products. Top {len(products)}:"]
        for p in products[:5]:
            lines.append(
                f"  id={p['id']} {p['name'][:50]} ৳{p.get('cheapest_price','?')} @ {p.get('cheapest_retailer','?')}"
            )
        return "\n".join(lines)

    if tool_name == "get_product_details":
        p = result
        listings = p.get("listings", [])
        lines = [f"Product id={p.get('id')} '{p.get('name','')}' ৳{p.get('cheapest_price')} @ {p.get('cheapest_retailer')}"]
        for l in listings[:4]:
            lines.append(f"  {l['retailer']}: ৳{l['price_bdt']} in_stock={l['in_stock']}")
        return "\n".join(lines)

    if tool_name == "get_price_history":
        return (
            f"Price history: current=৳{result.get('current_price')} "
            f"low=৳{result.get('all_time_low')} high=৳{result.get('all_time_high')} "
            f"trend={result.get('trend','?')}. {result.get('data_points',0)} data points."
        )

    if tool_name == "check_compatibility":
        issues = result.get("issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        warns  = [i for i in issues if i["level"] == "warn"]
        lines  = [f"Compat: {len(errors)} error(s), {len(warns)} warning(s). Est {result.get('estimated_watts')}W, recommend {result.get('recommended_psu')}W PSU."]
        for i in errors + warns:
            lines.append(f"  [{i['level']}] {i['title']}: {i['detail']}")
        return "\n".join(lines)

    if tool_name == "plan_build":
        slots = result.get("slots", [])
        total = result.get("total_cost")
        lines = [f"Build plan ({result.get('profile')}): total ৳{total}, within_budget={result.get('within_budget')}."]
        for s in slots:
            lines.append(f"  {s['slot']}: {s['product_name'][:40]} ৳{s.get('cheapest_price','?')}")
        compat = result.get("compatibility", {})
        if compat.get("has_errors"):
            lines.append("  WARNING: compatibility issues detected.")
        return "\n".join(lines)

    if tool_name == "get_deals":
        deals = result.get("deals", [])
        lines = [f"Deals: {len(deals)} price drops found."]
        for d in deals[:5]:
            lines.append(f"  {d.get('name','')[:40]} ৳{d.get('current_price')} (↓{d.get('drop_pct')}%)")
        return "\n".join(lines)

    # Fallback: truncate to 800 chars
    raw = json.dumps(result, default=str)
    return raw[:800] + ("..." if len(raw) > 800 else "")


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

def run(
    message: str,
    history: list[dict] | None = None,
    context: dict | None = None,
    conn=None,
) -> dict:
    """
    Run the agent for one user turn.

    Args:
        message:  The user's message.
        history:  Prior conversation messages [{role, content}].
        context:  Optional UI context: {category, filters, build_slots}.
                  build_slots: {slot_name: product_id} for the current build.
        conn:     DB connection. If None, one is opened internally.

    Returns:
        {
            "text":    str,          # agent's natural-language response
            "blocks":  list[dict],   # rich UI blocks to render
            "actions": list[dict],   # UI directives to execute
        }
    """
    history = history or []
    context = context or {}

    # Build context injection for the system prompt
    ctx_parts = []
    if context.get("category"):
        ctx_parts.append(f"User is currently browsing: {context['category']}")
    if context.get("filters"):
        ctx_parts.append(f"Active filters: {json.dumps(context['filters'])}")
    if context.get("build_slots"):
        ctx_parts.append(f"Current build slots: {json.dumps(context['build_slots'])}")

    system_content = SYSTEM_PROMPT
    if ctx_parts:
        system_content += "\n\nCurrent UI context:\n" + "\n".join(ctx_parts)

    # Assemble messages for the LLM
    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    tier = "reason" if _needs_reason_model(message, history) else "fast"

    blocks: list[dict] = []
    actions: list[dict] = []

    # Open a DB connection if not provided
    _close_conn = False
    if conn is None:
        conn = database.get_db().__enter__()
        _close_conn = True

    try:
        for iteration in range(MAX_ITERS):
            result = llm.complete(
                messages=messages,
                tools=tools.TOOLS,
                model_tier=tier,
                max_tokens=1024,
                temperature=0.1,
            )

            # If no tool calls → this is the final answer
            if not result.tool_calls:
                text, actions = _extract_actions(result.text)
                return {"text": text, "blocks": blocks, "actions": actions}

            # Append the assistant's tool-call turn to message history
            # (OpenAI format: assistant message with tool_calls array)
            assistant_msg: dict = {
                "role": "assistant",
                "content": result.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in result.tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Execute each tool call and collect results
            for tc in result.tool_calls:
                tool_result = tools.execute_tool(conn, tc.name, tc.arguments)

                # Build UI blocks from tool results
                factory = _BLOCK_FACTORIES.get(tc.name)
                if factory and not tool_result.get("error"):
                    blocks.append(factory(tool_result))

                # Append a compact summary to messages (full result is in blocks for the UI)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": _summarize_for_llm(tc.name, tool_result),
                })

        # Max iterations reached — ask the model for a final summary
        messages.append({
            "role": "user",
            "content": "Please give your final answer now based on the information gathered.",
        })
        result = llm.complete(
            messages=messages,
            tools=None,  # no more tool calls
            model_tier=tier,
            max_tokens=1024,
            temperature=0.2,
        )
        text, actions = _extract_actions(result.text)
        return {"text": text, "blocks": blocks, "actions": actions}

    finally:
        if _close_conn:
            try:
                conn.__exit__(None, None, None)
            except Exception:
                pass
