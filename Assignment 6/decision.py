"""
decision.py
Decision role — given one pending goal, choose: answer now OR call a tool.

Uses native tool calling (tools=mcp_tools, tool_choice="auto") via the gateway.
Routes through auto_route="decision" so the gateway router picks the tier.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

_GW_PATH = Path(__file__).parent / "llm_gatewayV3"
if str(_GW_PATH) not in sys.path:
    sys.path.insert(0, str(_GW_PATH))

from client import LLM  # noqa: E402

_llm = LLM()
_MAX_ARTIFACT_CHARS = 80_000

_SYSTEM = """\
You are the Decision role in a cognitive agent. You have ONE goal to work on.
Choose exactly ONE action: answer the goal directly, OR call one of the available tools.

RULES:
1. Answer directly when memory hits or ATTACHED ARTIFACTS contain enough information.
2. art: prefixed strings are artifact IDs — NOT valid file paths or URLs.
   Artifact bytes appear in the ATTACHED ARTIFACTS section. Read them there; never pass
   an art: string as a tool argument.
3. Substantive answers: at least 3 sentences or a numbered list of items.
4. Call at most ONE tool per response. Never call multiple tools.
5. For synthesis goals (extract, list, compare, summarise, choose, analyse, agree on):
   if ATTACHED ARTIFACTS are present — read them and answer directly. Do not re-fetch.
"""


def _llm_retry(prompt: str, *, retries: int = 5, **kw) -> dict:
    for i in range(retries):
        try:
            return _llm.chat(prompt, **kw)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503) and i < retries - 1:
                wait = 10 * (2 ** i)
                print(f"  [decision] throttled, retry in {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("retries exhausted")


def next_step(
    goal: Goal,
    hits: list[MemoryItem],
    attached: list[tuple[str, bytes]],
    history: list[dict],
    mcp_tools: list[dict],
) -> DecisionOutput:
    """Decide next action for one pending goal."""

    hits_lines = [
        f"  [{h.kind}] {h.descriptor}" + (f" [artifact: {h.artifact_id}]" if h.artifact_id else "")
        for h in hits
    ]
    hits_block = "\n".join(hits_lines) or "  (none)"

    hist_lines = []
    for ev in history[-8:]:
        if ev.get("kind") == "action":
            hist_lines.append(
                f"  iter{ev['iter']} {ev['tool']}"
                f"({str(ev.get('arguments', ''))[:60]}) "
                f"→ {ev.get('result_descriptor', '')[:180]}"
            )
        elif ev.get("kind") == "answer":
            hist_lines.append(f"  iter{ev['iter']} ANSWER: {ev.get('text', '')[:180]}")
    history_block = "\n".join(hist_lines) or "  (none)"

    artifact_block = ""
    if attached:
        parts = []
        for art_id, data in attached:
            try:
                content = data.decode("utf-8", errors="replace")
            except Exception:
                content = f"[binary, {len(data)} bytes]"
            if len(content) > _MAX_ARTIFACT_CHARS:
                content = content[:_MAX_ARTIFACT_CHARS] + "\n...[truncated]"
            parts.append(f"=== ARTIFACT {art_id} ===\n{content}")
        artifact_block = "\n\nATTACHED ARTIFACTS:\n" + "\n".join(parts)

    prompt = (
        f"CURRENT GOAL: {goal.text}\n\n"
        f"MEMORY HITS:\n{hits_block}\n\n"
        f"RECENT HISTORY:\n{history_block}"
        f"{artifact_block}"
    )

    resp = _llm_retry(
        prompt,
        system=_SYSTEM,
        provider="g",
        model="gemini-3.1-flash-lite",
        tools=mcp_tools,
        tool_choice="auto",
        max_tokens=4096,
        temperature=0.2,
    )

    tool_calls = resp.get("tool_calls") or []
    if tool_calls:
        tc = tool_calls[0]
        name = tc.get("name", "")
        arguments = tc.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        if name:
            return DecisionOutput(tool_call=ToolCall(name=name, arguments=arguments))

    text = (resp.get("text") or "").strip()
    if text:
        return DecisionOutput(answer=text)

    return DecisionOutput(answer="Could not determine next action. Try rephrasing your query.")
