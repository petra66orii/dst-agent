"""Claude research agent: a tool-use loop over src/tools.py. Used by the Discord bot."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from datetime import datetime, timezone

from src import tools
from src.risk import rules_text
from src.settings import ANTHROPIC_API_KEY, BENCHMARK

AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-5-5")
MAX_TOOL_ROUNDS = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "8"))
MAX_TOKENS = 1500

SYSTEM = f"""You are DST, Petra's US-stock research analyst, chatting in Discord.

How you work:
- Get facts from tools before answering; never state a price, filing, insider trade or news item
  you didn't get from a tool in this conversation. If a tool fails, say what's missing.
- Cite: put the filing or article URL next to any factual claim (wrap URLs in <> to stop previews).
- Headlines with verified_source=false are rumours until a filing or verified outlet confirms them.
- Be sceptical of the bot's own signals: check get_scorecard before leaning on them, and say when the
  sample is too small to mean anything.
- Give both sides: the case for, the case against, and what would prove the idea wrong.
- Trade ideas: give entry, stop, target, horizon and position size, run check_trade_idea, and only
  call log_trade_idea when Petra explicitly asks you to log/record it. Logging is not an order;
  Petra places any real trade herself.
- Hard risk rules (enforced in code, don't argue with them): {rules_text()}
- Benchmark: {BENCHMARK}. Write in UK English, casual and concise. Discord messages: short
  paragraphs or bullets, no tables, under ~1,500 characters unless asked for depth."""

_PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _schema(fn) -> dict:
    sig = inspect.signature(inspect.unwrap(fn))
    props, required = {}, []
    for name, p in sig.parameters.items():
        ann = p.annotation if p.annotation is not inspect.Parameter.empty else str
        if isinstance(ann, str):  # postponed annotations
            ann = {"str": str, "int": int, "float": float, "bool": bool}.get(ann, str)
        props[name] = {"type": _PY_TO_JSON.get(ann, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(name)
        else:
            props[name]["default"] = p.default
    return {"type": "object", "properties": props, "required": required}


TOOL_SPECS = [{"name": f.__name__, "description": (inspect.getdoc(f) or f.__name__)[:1000],
               "input_schema": _schema(f)} for f in tools.ALL_TOOLS]
TOOL_FNS = {f.__name__: f for f in tools.ALL_TOOLS}


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(history: list[dict], on_tool=None) -> tuple[str, list[dict]]:
    """Run one user turn. `history` is the Anthropic messages list ending with the user message.
    Returns (reply_text, updated_history)."""
    if not ANTHROPIC_API_KEY:
        return "I need ANTHROPIC_API_KEY set before I can think. 🙃", history
    client = _client()
    messages = list(history)
    system = SYSTEM + f"\nCurrent time (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M}."
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.messages.create(model=AGENT_MODEL, max_tokens=MAX_TOKENS, system=system,
                                      tools=TOOL_SPECS, messages=messages)
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        if resp.stop_reason != "tool_use":
            text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
            return text or "(no reply)", messages
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if on_tool:
                on_tool(block.name, block.input)
            fn = TOOL_FNS.get(block.name)
            args = dict(block.input)
            if block.name == "log_trade_idea":
                args["model"] = AGENT_MODEL
            try:
                out = fn(**args) if fn else {"error": f"unknown tool {block.name}"}
            except TypeError as e:  # bad arguments from the model
                out = {"error": str(e)}
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(out, default=str)[:20000]})
        messages.append({"role": "user", "content": results})
    return "I hit my tool-call limit for one question; try narrowing it down.", messages


async def arun(history: list[dict], on_tool=None) -> tuple[str, list[dict]]:
    return await asyncio.to_thread(run, history, on_tool)


def trim_history(messages: list[dict], max_turns: int = 12) -> list[dict]:
    """Keep the last N user text turns (with their tool exchanges) to bound cost."""
    starts = [i for i, m in enumerate(messages)
              if m["role"] == "user" and isinstance(m["content"], str)]
    if len(starts) <= max_turns:
        return messages
    return messages[starts[-max_turns]:]
