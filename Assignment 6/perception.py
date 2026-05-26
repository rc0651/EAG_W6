"""
perception.py
Perception role — orchestrator, runs every iteration.

First call: decomposes the query into 1-5 goals.
Subsequent calls: preserves goal order, updates done flags (sticky), attaches artifacts.

Safety properties:
  - Goal IDs assigned by the loop from prior_goals (positional identity).
    The LLM output schema has no id field — prevents hallucinated stale ids.
  - Artifact attachment uses integer index → loop resolves to actual art: handle.
  - Once done=true, never reverted (enforced in Python after LLM output).
  - temperature=1.0 prevents Gemini flash-lite from repeating structured output.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

from schemas import Goal, MemoryItem, Observation

_GW_PATH = Path(__file__).parent / "llm_gatewayV3"
if str(_GW_PATH) not in sys.path:
    sys.path.insert(0, str(_GW_PATH))

from client import LLM  # noqa: E402

_llm = LLM()

_GOAL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "done": {"type": "boolean"},
                    "artifact_index": {
                        "type": "integer",
                        "description": (
                            "-1 = no attachment. "
                            "0+ = index from the ARTIFACT HITS list."
                        ),
                    },
                },
                "required": ["text", "done", "artifact_index"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["goals"],
    "additionalProperties": False,
}

_SYSTEM = """\
You are the Perception role in a cognitive agent. Each iteration you receive:
  - The original user query
  - Memory hits (some have stored artifacts, shown with an integer artifact_index)
  - Prior goals (if any) with done/pending status
  - History of recent tool calls and answers

RESPONSIBILITIES:

1. FIRST CALL (no prior goals):
   Decompose the query into 1-5 short imperative goals (verb + object).
   Set done=false and artifact_index=-1 for all.

2. SUBSEQUENT CALLS (prior goals exist):
   Keep EXACTLY the same goals in EXACTLY the same order.
   Do NOT add, remove, or reorder goals.
   Mark done=true if the history shows the goal is satisfied.
   STICKY: once done=true, never set it back to false.

3. ARTIFACT ATTACHMENT (first pending goal only):
   If the first pending goal requires content from a previously fetched artifact
   (keywords: extract, summarise, compare, list, analyse, choose, synthesise,
   tell me, agree on, in common, decide)
   AND an artifact appears in memory hits — set artifact_index to its integer index.
   SYNTHESIS RULE: any goal containing the above keywords + existing artifacts
   → set artifact_index to the most recent artifact's index.
   Otherwise set artifact_index=-1.

Output JSON only. No explanation.
"""


def _llm_retry(prompt: str, *, retries: int = 3, **kw) -> dict:
    for i in range(retries):
        try:
            return _llm.chat(prompt, **kw)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503) and i < retries - 1:
                wait = 10 * (2 ** i)
                print(f"  [perception] throttled, retry in {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("retries exhausted")


def observe(
    query: str,
    hits: list[MemoryItem],
    history: list[dict],
    prior_goals: list[Goal],
    run_id: str,
) -> Observation:
    """Run Perception for one agent iteration."""

    # Build numbered artifact list for LLM reference
    artifact_hits: list[tuple[int, MemoryItem]] = []
    hits_lines: list[str] = []
    art_idx = 0
    for item in hits:
        if item.artifact_id:
            hits_lines.append(
                f"  [{item.kind}] artifact_index={art_idx} | {item.descriptor} | id={item.artifact_id}"
            )
            artifact_hits.append((art_idx, item))
            art_idx += 1
        else:
            hits_lines.append(f"  [{item.kind}] {item.descriptor}")
    hits_block = "\n".join(hits_lines) or "  (none)"

    if prior_goals:
        goal_lines = [
            f"  {'[done]' if g.done else '[pending]'} {g.id}: {g.text}"
            for g in prior_goals
        ]
        goals_block = "PRIOR GOALS:\n" + "\n".join(goal_lines)
    else:
        goals_block = "PRIOR GOALS: (none — first call, decompose the query)"

    hist_lines = []
    for ev in history[-10:]:
        if ev.get("kind") == "action":
            hist_lines.append(
                f"  iter{ev['iter']} TOOL {ev['tool']}"
                f"({str(ev.get('arguments', ''))[:60]}) "
                f"→ {ev.get('result_descriptor', '')[:180]}"
            )
        elif ev.get("kind") == "answer":
            hist_lines.append(
                f"  iter{ev['iter']} ANSWER for {ev['goal_id']}: "
                f"{ev.get('text', '')[:180]}"
            )
    history_block = ("HISTORY:\n" + "\n".join(hist_lines)) if hist_lines else "HISTORY: (empty)"

    prompt = (
        f"USER QUERY: {query}\n\n"
        f"MEMORY HITS (with artifact_index where applicable):\n{hits_block}\n\n"
        f"{goals_block}\n\n"
        f"{history_block}\n\n"
        "Emit the goal list as JSON. "
        "artifact_index: -1 for no attachment, or the integer index shown above."
    )

    resp = _llm_retry(
        prompt,
        system=_SYSTEM,
        provider="g",
        model="gemini-3.1-flash-lite",
        temperature=1.0,
        max_tokens=1024,
        response_format={"type": "json_schema", "schema": _GOAL_OUTPUT_SCHEMA},
    )

    try:
        data = resp.get("parsed") or json.loads(resp.get("text", "{}"))
        raw_goals = data.get("goals", [])
    except Exception:
        raw_goals = []

    if not raw_goals and prior_goals:
        raw_goals = [{"text": g.text, "done": g.done, "artifact_index": -1} for g in prior_goals]
    elif not raw_goals:
        raw_goals = [{"text": query, "done": False, "artifact_index": -1}]

    art_lookup: dict[int, str] = {
        i: item.artifact_id
        for i, item in artifact_hits
        if item.artifact_id
    }

    goals: list[Goal] = []
    for i, rg in enumerate(raw_goals):
        # Positional identity: id from prior_goals if exists, else assign g{n}
        if i < len(prior_goals):
            gid = prior_goals[i].id
            is_done = prior_goals[i].done or bool(rg.get("done", False))
        else:
            gid = f"g{i + 1}"
            is_done = bool(rg.get("done", False))

        # Resolve integer artifact_index to actual art: handle
        ai = rg.get("artifact_index", -1)
        attach: str | None = None
        if isinstance(ai, int) and ai >= 0:
            attach = art_lookup.get(ai)

        goals.append(Goal(
            id=gid,
            text=rg.get("text", f"goal {i + 1}"),
            done=is_done,
            attach_artifact_id=attach,
        ))

    return Observation(goals=goals)
