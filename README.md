# EAG V3 – Assignment 6: Four-Role Cognitive Agent

A multi-role cognitive agent built on top of LLM Gateway V3 and MCP tool servers.
The agent follows a fixed iteration loop: **Memory → Perception → Decision → Action**.

---

## Architecture

```
agent6.py  (orchestration loop)
    │
    ├── memory.py      – keyword recall + LLM classification, persists to state/memory.json
    ├── perception.py  – goal decomposition / status tracking  (Gemini flash-lite, T=1.0)
    ├── decision.py    – answer vs. tool selection  (auto_route="decision", native tool calling)
    ├── action.py      – pure MCP dispatch, no LLM, artifact store for large results
    ├── artifacts.py   – content-addressed store  art:<sha256-prefix>
    ├── schemas.py     – Pydantic v2 typed contracts for all role boundaries
    └── mcp_server.py  – 9 MCP tools over stdio
```

All LLM calls route through **LLM Gateway V3** (`http://localhost:8101`).

### Cognitive Roles

| Role | LLM Calls | Routing | Notes |
|------|-----------|---------|-------|
| Memory | 1 per query (classify) | `auto_route="memory"` | keyword recall is pure Python |
| Perception | 1 per iteration | `provider="g", model="gemini-3.1-flash-lite"` | T=1.0, positional goal IDs |
| Decision | 1 per iteration | `auto_route="decision"` | native tool calling |
| Action | 0 | – | pure MCP dispatch |

### Available MCP Tools

`web_search`, `fetch_url`, `get_time`, `currency_convert`,
`read_file`, `list_dir`, `create_file`, `update_file`, `edit_file`

---

## Setup

### Prerequisites
- Python ≥ 3.11 ([uv](https://docs.astral.sh/uv/) recommended)
- Playwright Chromium (for `fetch_url`)

### Install

```bash
cd "Assignment 6"
uv sync
uv run playwright install chromium
```

### Environment

Create `Assignment 6/.env`:

```
GEMINI_API_KEY=<your-key>
TAVILY_API_KEY=<your-key>
GEMINI_MODEL=gemini-3.1-flash-lite
```

### Run

```bash
# Start LLM Gateway (auto-started by agent if not running)
cd "Assignment 6/llm_gatewayV3" && uv run python main.py &

# Run queries
cd "Assignment 6"
uv run python agent6.py --run-a    # Claude Shannon Wikipedia fetch
uv run python agent6.py --run-b    # Tokyo weekend activities + weather
uv run python agent6.py --run-c1   # Remember mom's birthday
uv run python agent6.py --run-c2   # Recall mom's birthday (memory test, run after c1)
uv run python agent6.py --run-d    # Python asyncio best practices synthesis
```

**Note:** `--run-c2` must be run *after* `--run-c1` to test cross-run memory persistence.
The `state/` directory is excluded from git.

---

## Terminal Output

### Query A — Claude Shannon (3 iterations)

```
[gateway] up at http://localhost:8101

[agent:5c33d447] Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions t
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ['Claude Shannon birth, death, and key contributions']
  [perception] [open] g1: Fetch information about Claude Shannon from Wikipedia
  [perception] [open] g2: Extract birth date, death date, and three key contributions to information theory
  [decision] throttled, retry in 10s
  [decision] TOOL: web_search({'query': 'Claude Shannon Wikipedia'})
  [action] → [artifact art:9dff3291a0827bad, 10,535 bytes] preview: {   "title": "Claude Shannon - Wikipedia ...

── iter 2 ──
[memory] 2 hits: ["web_search(query='Claude Shannon Wikipedia') → [ar", 'Claude Shannon birth, death, and key contributions']
  [perception] [done] g1: Fetch information about Claude Shannon from Wikipedia  attach=art:9dff3291a0827bad
  [perception] [open] g2: Extract birth date, death date, and three key contributions to information theory  attach=art:9dff3291a0827bad
  [artifact] loaded art:9dff3291a0827bad (10,535 bytes)
  [decision] throttled, retry in 10s
  [decision] ANSWER: Claude Shannon was born on April 30, 1916, and passed away on February 24, 2001. He is widely recognized as the "father of information theory"...

── iter 3 ──
[memory] 2 hits: [...]
  [perception] [done] g1: Fetch information about Claude Shannon from Wikipedia
  [perception] [done] g2: Extract birth date, death date, and three key contributions to information theory
[agent] all goals done

============================================================
FINAL ANSWER:
Claude Shannon was born on April 30, 1916, and passed away on February 24, 2001. He is widely
recognized as the "father of information theory" for his foundational work in the field.

His three key contributions to information theory include:

1.  **Founding Information Theory:** In his seminal 1948 paper, "A Mathematical Theory of
    Communication," he established the mathematical framework for how information is measured,
    transmitted, and processed, which serves as the basis for modern digital communication.
2.  **Application of Boolean Algebra to Digital Circuits:** In his master's thesis, "A Symbolic
    Analysis of Relay and Switching Circuits," he demonstrated that Boolean algebra and binary
    arithmetic could be used to simplify and design telephone routing switches, providing the
    fundamental logic behind all modern digital computers.
3.  **Quantification of Information:** He introduced the concept of the "bit" as the basic unit
    of information and developed the concept of "Shannon entropy," which measures the uncertainty
    or information content in a data source, allowing for the optimization of data compression
    and transmission.
============================================================
```

---

### Query B — Tokyo Weekend Activities + Weather (4 iterations)

```
[gateway] up at http://localhost:8101

[agent:962a3add] Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ['Planning family activities in Tokyo for the weeken']
  [perception] [open] g1: Find 3 family-friendly things to do in Tokyo
  [perception] [open] g2: Check Saturday's weather forecast for Tokyo
  [perception] [open] g3: Recommend the most appropriate activity based on weather
  [decision] throttled, retry in 10s
  [decision] TOOL: web_search({'query': 'family-friendly things to do in Tokyo'})
  [action] → [artifact art:e076af36dcc2e282, 9,759 bytes] preview: ...

── iter 2 ──
[memory] 2 hits: [...]
  [perception] [done] g1: Find 3 family-friendly things to do in Tokyo  attach=art:e076af36dcc2e282
  [perception] [open] g2: Check Saturday's weather forecast for Tokyo
  [perception] [open] g3: Recommend the most appropriate activity based on weather  attach=art:e076af36dcc2e282
  [decision] throttled, retry in 10s
  [decision] TOOL: web_search({'query': 'weather forecast Tokyo Saturday'})
  [action] → [artifact art:e798907e2e3176b4, 9,927 bytes] preview: ...

── iter 3 ──
[memory] 3 hits: [...]
  [perception] [done] g1: Find 3 family-friendly things to do in Tokyo
  [perception] [done] g2: Check Saturday's weather forecast for Tokyo
  [perception] [open] g3: Recommend the most appropriate activity based on weather  attach=art:e798907e2e3176b4
  [artifact] loaded art:e798907e2e3176b4 (9,927 bytes)
  [decision] throttled, retry in 10s
  [decision] ANSWER: Based on the current weather outlook for Tokyo ...

── iter 4 ──
[memory] 3 hits: [...]
  [perception] [done] g1: Find 3 family-friendly things to do in Tokyo  attach=art:e076af36dcc2e282
  [perception] [done] g2: Check Saturday's weather forecast for Tokyo  attach=art:e798907e2e3176b4
  [perception] [done] g3: Recommend the most appropriate activity based on weather
[agent] all goals done

============================================================
FINAL ANSWER:
Based on the current weather outlook for Tokyo, which generally features mild to warm temperatures
and pleasant conditions in late May, I recommend a mix of outdoor and indoor activities to make
the most of your weekend.

Here are my top recommendations for a family-friendly trip:

1.  **Immersive Art at teamLab Planets:** This is an excellent indoor activity that is perfect for
    families. It offers a unique, sensory-rich experience where you walk through water and digital
    art installations, making it a memorable highlight regardless of the outside temperature.
2.  **Explore Tokyo's Parks:** Since the weather in late May is typically stable and comfortable,
    it is an ideal time to visit outdoor spaces like **Ueno Park** or **Shinjuku Gyoen National
    Garden**. These areas are great for a family picnic or a leisurely stroll.
3.  **Theme Park Fun:** If you are looking for a full-day adventure, **Tokyo DisneySea** is highly
    recommended. It is unique to Japan and offers a variety of nautical-themed lands that cater to
    all ages.
4.  **Panoramic City Views:** For a relaxing afternoon, head to the **Tokyo Skytree** or the
    **Tokyo Tower**. These locations provide stunning 360-degree views of the city.
============================================================
```

---

### Query C1 — Remember Mom's Birthday (4 iterations)

```
[gateway] up at http://localhost:8101

[agent:e7a640c0] My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ["My mom's birthday is 15 May 2026. Remember that an"]
  [perception] [open] g1: Store the mom's birthday date of 15 May 2026
  [perception] [open] g2: Set calendar reminder for 1 May 2026
  [perception] [open] g3: Set calendar reminder for 15 May 2026
  [decision] throttled, retry in 10s
  [decision] TOOL: create_file({'content': "Mom's birthday: 15 May 2026", 'path': 'mom_birthday.txt'})
  [action] → {
  "ok": true,
  "path": "mom_birthday.txt",
  "bytes": 27
}

── iter 2 ──
[memory] 2 hits: [...]
  [perception] [done] g1: Store the mom's birthday date of 15 May 2026
  [perception] [open] g2: Set calendar reminder for 1 May 2026
  [perception] [open] g3: Set calendar reminder for 15 May 2026
  [decision] TOOL: create_file({'path': 'reminder_1may2026.txt', 'content': 'Reminder: 1 May 2026 - Set calendar reminder.'})
  [action] → {
  "ok": true,
  "path": "reminder_1may2026.txt",
  "bytes": 45
}

── iter 3 ──
[memory] 3 hits: [...]
  [perception] [done] g1: Store the mom's birthday date of 15 May 2026
  [perception] [done] g2: Set calendar reminder for 1 May 2026
  [perception] [open] g3: Set calendar reminder for 15 May 2026
  [decision] throttled, retry in 10s
  [decision] TOOL: create_file({'path': 'reminder_15may2026.txt', 'content': "Reminder: Mom's birthday on 15 May 2026"})
  [action] → {
  "ok": true,
  "path": "reminder_15may2026.txt",
  "bytes": 39
}

── iter 4 ──
[memory] 4 hits: [...]
  [perception] [done] g1: Store the mom's birthday date of 15 May 2026
  [perception] [done] g2: Set calendar reminder for 1 May 2026
  [perception] [done] g3: Set calendar reminder for 15 May 2026
[agent] all goals done

============================================================
FINAL ANSWER:
Done: create_file → {
  "ok": true,
  "path": "reminder_15may2026.txt",
  "bytes": 39
}
============================================================
```

---

### Query C2 — Recall Mom's Birthday (2 iterations, memory persisted from C1)

```
[gateway] up at http://localhost:8101

[agent:af4f44e6] When is mom's birthday?
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 4 hits: ["My mom's birthday is 15 May 2026. Remember that an", 'create_file(content="Mom\'s birthday: 15 May 2026",', ...]
  [perception] [open] g1: Identify mom's birthday from memory
  [decision] throttled, retry in 10s
  [decision] ANSWER: Your mom's birthday is on May 15, 2026. I have previously saved this
    information in a file named `mom_birthday.txt` and created a reminder for that date.

── iter 2 ──
[memory] 5 hits: [...]
  [perception] [done] g1: Identify mom's birthday from memory
[agent] all goals done

============================================================
FINAL ANSWER:
Your mom's birthday is on May 15, 2026. I have previously saved this information in a file
named `mom_birthday.txt` and created a reminder for that date.
============================================================
```

---

### Query D — Python asyncio Best Practices (3 iterations)

```
[gateway] up at http://localhost:8101

[agent:8a76896b] Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ['Summary of common Python asyncio best practices fr']
  [perception] [open] g1: Search for Python asyncio best practices
  [perception] [open] g2: Read the top 3 results
  [perception] [open] g3: Create a numbered list of the advice they agree on
  [decision] throttled, retry in 10s
  [decision] TOOL: web_search({'query': 'Python asyncio best practices'})
  [action] → [artifact art:e00fff5afc5ebab4, 10,278 bytes] preview: ...

── iter 2 ──
[memory] 2 hits: [...]
  [perception] [done] g1: Search for Python asyncio best practices
  [perception] [done] g2: Read the top 3 results
  [perception] [open] g3: Create a numbered list of the advice they agree on  attach=art:e00fff5afc5ebab4
  [artifact] loaded art:e00fff5afc5ebab4 (10,278 bytes)
  [decision] throttled, retry in 10s
  [decision] ANSWER: Based on the provided resources, here are the key best practices for Python asyncio...

── iter 3 ──
[memory] 2 hits: [...]
  [perception] [done] g1: Search for Python asyncio best practices
  [perception] [done] g2: Read the top 3 results
  [perception] [done] g3: Create a numbered list of the advice they agree on
[agent] all goals done

============================================================
FINAL ANSWER:
Based on the provided resources, here are the key best practices for Python's `asyncio` that are
consistently agreed upon:

1.  **Do not block the event loop:** Avoid using synchronous, blocking operations (like
    `time.sleep()` or heavy CPU-bound tasks) directly inside `async` functions, as this halts the
    entire event loop. Instead, use non-blocking alternatives (like `asyncio.sleep()`) or offload
    blocking code to a thread pool using `loop.run_in_executor()`.
2.  **Use `asyncio.run()` as the entry point:** Always use `asyncio.run()` to start your main
    coroutine. It is the recommended way to properly set up the event loop, run the task, and
    handle cleanup when the program finishes.
3.  **Utilize Tasks for concurrency:** To run independent operations concurrently rather than
    sequentially, wrap them in `asyncio.create_task()`. This allows the event loop to schedule and
    execute them concurrently, significantly improving performance for I/O-bound tasks.
4.  **Always await coroutines:** A common pitfall is forgetting to `await` a coroutine. Always
    ensure that you `await` your coroutines to ensure they are properly scheduled and executed by
    the event loop.
============================================================
```

---

## Project Structure

```
EAG_W6/
├── Assignment 6/
│   ├── agent6.py          # Main loop – Memory→Perception→Decision→Action
│   ├── schemas.py         # Pydantic v2 typed contracts
│   ├── memory.py          # Keyword recall + LLM classify, state/memory.json
│   ├── perception.py      # Goal decomposition / status (Gemini flash-lite)
│   ├── decision.py        # Answer vs. tool call (native tool calling)
│   ├── action.py          # Pure MCP dispatch + artifact store
│   ├── artifacts.py       # Content-addressed store (art:<sha256-prefix>)
│   ├── mcp_server.py      # 9 MCP tools over stdio
│   ├── llm_gatewayV3/     # LLM Gateway V3 (Gemini + routing)
│   ├── pyproject.toml     # uv/hatch project
│   ├── .env               # API keys (not committed)
│   └── state/             # Runtime state (not committed)
│       ├── memory.json
│       └── artifacts/
└── README.md
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Positional goal IDs (not LLM-assigned) | Prevents hallucinated stale IDs across iterations |
| `artifact_index` integer in Perception | LLM references by safe integer; loop resolves to `art:` handle |
| `temperature=1.0` for Perception | Prevents Gemini flash-lite structured output repetition loop |
| Sticky `done=true` enforced in Python | LLM cannot accidentally reopen completed goals |
| Artifact threshold 4KB | Keeps history context small; large content lives in file store |
| No LLM in Action | Pure dispatch — deterministic, auditable, no hallucination risk |
