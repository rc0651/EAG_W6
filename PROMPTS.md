# Perception and Decision – Prompts and Validation JSON

---

## 1. Perception Role

### System Prompt

```
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
```

### Example User Prompt (first call)

```
USER QUERY: Search for 'Python asyncio best practices', read the top 3 results,
and give me a short numbered list of the advice they agree on.

MEMORY HITS (with artifact_index where applicable):
  (none)

PRIOR GOALS: (none — first call, decompose the query)

HISTORY: (empty)

Emit the goal list as JSON. artifact_index: -1 for no attachment, or the integer index shown above.
```

### Validation JSON Schema

```json
{
  "type": "object",
  "properties": {
    "goals": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "properties": {
          "text": { "type": "string" },
          "done": { "type": "boolean" },
          "artifact_index": {
            "type": "integer",
            "description": "-1 = no attachment. 0+ = index from the ARTIFACT HITS list."
          }
        },
        "required": ["text", "done", "artifact_index"],
        "additionalProperties": false
      }
    }
  },
  "required": ["goals"],
  "additionalProperties": false
}
```

### Example Valid Output (first call)

```json
{
  "goals": [
    { "text": "Search for Python asyncio best practices", "done": false, "artifact_index": -1 },
    { "text": "Read the top 3 results", "done": false, "artifact_index": -1 },
    { "text": "Create a numbered list of the advice they agree on", "done": false, "artifact_index": -1 }
  ]
}
```

### Example Valid Output (subsequent call — synthesis goal with artifact)

```json
{
  "goals": [
    { "text": "Search for Python asyncio best practices", "done": true, "artifact_index": -1 },
    { "text": "Read the top 3 results", "done": true, "artifact_index": -1 },
    { "text": "Create a numbered list of the advice they agree on", "done": false, "artifact_index": 0 }
  ]
}
```

**Safety properties enforced by the Python loop:**
- Goal IDs assigned by position from `prior_goals` (not by the LLM) — prevents hallucinated stale IDs
- `artifact_index` integer is resolved to actual `art:<sha256-prefix>` handle by the loop — LLM never sees raw artifact handles
- `done=true` is sticky — once set, Python never reverts it even if LLM outputs `done=false`

---

## 2. Decision Role

### System Prompt

```
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
```

### Example User Prompt (tool call path)

```
CURRENT GOAL: Search for Python asyncio best practices

MEMORY HITS:
  (none)

RECENT HISTORY:
  (none)
```

### Example User Prompt (answer path — artifact attached)

```
CURRENT GOAL: Create a numbered list of the advice they agree on

MEMORY HITS:
  [tool_outcome] artifact_index=0 | web_search(query='Python asyncio best pr') → [artifact art:e00fff5afc5ebab4] | id=art:e00fff5afc5ebab4

RECENT HISTORY:
  iter1 web_search(query='Python asyncio best practices') → [artifact art:e00fff5afc5ebab4, 10,278 bytes]

ATTACHED ARTIFACTS:
=== ARTIFACT art:e00fff5afc5ebab4 ===
{   "title": "Asyncio best practices - Async-SIG - Discussions on Python.org",
    "url": "https://discuss.python.org/t/asyncio-best-practices/12576",
    "snippet": "# Asyncio best practices\n\nSo I thought it'd be great to catalog some of the best
    practices for asyncio..."
    ... (truncated at 80,000 chars)
}
```

### Validation Schema

Decision uses **native tool calling** via the gateway (`tool_choice="auto"`).
The gateway returns either a `tool_calls` array or a `text` field.

**Tool call response structure (from gateway):**
```json
{
  "tool_calls": [
    {
      "name": "web_search",
      "arguments": {
        "query": "Python asyncio best practices"
      }
    }
  ]
}
```

**Text answer response structure (from gateway):**
```json
{
  "text": "Based on the provided resources, here are the key best practices for Python asyncio:\n\n1. **Do not block the event loop** ...",
  "tool_calls": []
}
```

**Python parsing logic (decision.py):**
```python
tool_calls = resp.get("tool_calls") or []
if tool_calls:
    tc = tool_calls[0]         # use only the first tool call
    name = tc.get("name", "")
    arguments = tc.get("arguments") or {}
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    return DecisionOutput(tool_call=ToolCall(name=name, arguments=arguments))

text = (resp.get("text") or "").strip()
if text:
    return DecisionOutput(answer=text)
```

**Pydantic v2 contract at Decision output boundary:**
```python
class ToolCall(BaseModel):
    name: str
    arguments: dict

class DecisionOutput(BaseModel):
    answer: str | None = None
    tool_call: ToolCall | None = None

    @property
    def is_answer(self) -> bool:
        return self.answer is not None
```

---

## 3. LLM Gateway Routing Summary

| Role | Route | Provider | Model |
|------|-------|----------|-------|
| Memory classify | `auto_route="memory"` | Gateway selects | flash-lite tier |
| Memory relevant | `auto_route="memory"` | Gateway selects | flash-lite tier |
| Perception | `provider="g"` | Gemini | `gemini-3.1-flash-lite` |
| Decision | `auto_route="decision"` | Gateway selects | decision tier (native tool calling) |

---

## 4. Observation Schema (Perception Output)

```python
class Goal(BaseModel):
    id: str                              # assigned by loop: g1, g2, ...
    text: str
    done: bool = False
    attach_artifact_id: str | None = None  # resolved from artifact_index by loop

class Observation(BaseModel):
    goals: list[Goal]

    @property
    def all_done(self) -> bool:
        return all(g.done for g in self.goals)

    def next_unfinished(self) -> Goal | None:
        return next((g for g in self.goals if not g.done), None)
```
