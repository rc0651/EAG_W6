# EAG V3 – Assignment 6: Four-Role Cognitive Agent

A multi-role cognitive agent built on top of LLM Gateway V3 and MCP tool servers.
The agent follows a fixed iteration loop: **Memory → Perception → Decision → Action**.

🎥 **Demo Video:** https://youtu.be/IORlTTgRcXU

---

## Architecture

```
agent6.py  (orchestration loop)
    │
    ├── memory.py      – keyword recall + LLM classification, persists to state/memory.json
    ├── perception.py  – goal decomposition / status tracking  (Gemini flash-lite, T=1.0)
    ├── decision.py    – answer vs. tool selection  (gemini-3.1-flash-lite, native tool calling)
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
| Decision | 1 per iteration | `provider="g", model="gemini-3.1-flash-lite"` | native tool calling |
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
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

### Run

```bash
# Start LLM Gateway (Tab 1)
cd "Assignment 6"
uv run python llm_gatewayV3/main.py

# Run queries (Tab 2)
cd "Assignment 6"
uv run python agent6.py --run-a    # Claude Shannon Wikipedia fetch
uv run python agent6.py --run-b    # Tokyo weekend activities + weather
uv run python agent6.py --run-c1   # Remember mom's birthday
uv run python agent6.py --run-c2   # Recall mom's birthday (run after c1)
uv run python agent6.py --run-d    # Python asyncio best practices synthesis
```

**Note:** `--run-c2` must be run *after* `--run-c1` without clearing state — this tests cross-run memory persistence. The `state/` directory is excluded from git.

---

## Terminal Output

### Query A — Claude Shannon (2 iterations)

**Query:** `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.`

```
[gateway] up at http://localhost:8101

[agent:79a1f6ca] Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions t
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ['Claude Shannon birth, death, and key contributions']
  [perception] [open] g1: Fetch information about Claude Shannon from Wikipedia
  [perception] [open] g2: Extract birth date, death date, and three key contributions to information theory
  [decision] TOOL: web_search({'query': 'Claude Shannon Wikipedia'})
  [action] → [artifact art:51b1b468dd59b9ab, 8,149 bytes] preview: {   "title": "Claude Shannon - Wikipedia", ...

── iter 2 ──
[memory] 2 hits: ["web_search(query='Claude Shannon Wikipedia') → [ar", 'Claude Shannon birth, death, and key contributions']
  [perception] [done] g1: Fetch information about Claude Shannon from Wikipedia
  [perception] [open] g2: Extract birth date, death date, and three key contributions to information theory  attach=art:51b1b468dd59b9ab
  [artifact] loaded art:51b1b468dd59b9ab (8,149 bytes)
  [decision] ANSWER: Claude Shannon was born on April 30, 1916, and he passed away on February 24, 2001. ...
[agent] all goals done

============================================================
FINAL ANSWER:
Claude Shannon was born on April 30, 1916, and he passed away on February 24, 2001.

His key contributions to the field of information theory include:

1.  **Founding the Field:** He established the discipline of information theory with his landmark
    1948 paper, "A Mathematical Theory of Communication," which provided a formal mathematical
    framework for the quantification, storage, and communication of information.
2.  **The Noisy-Channel Coding Theorem:** He proved this fundamental theorem, which demonstrated
    that for any given communication channel, there is a maximum rate (channel capacity) at which
    information can be transmitted with an arbitrarily low probability of error, despite the
    presence of noise.
3.  **Quantification of Information (Entropy):** He introduced the concept of entropy as a measure
    of the uncertainty or information content in a message, providing a rigorous way to measure
    information that remains the backbone of the field today.
============================================================
```

---

### Query B — Tokyo Weekend Activities + Weather (3 iterations)

**Query:** `Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.`

```
[gateway] up at http://localhost:8101

[agent:50212c33] Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ['Planning family activities in Tokyo for the weeken']
  [perception] [open] g1: Find 3 family-friendly activities in Tokyo for the weekend
  [perception] [open] g2: Check Tokyo weather forecast for Saturday
  [perception] [open] g3: Recommend the most appropriate activity based on weather
  [decision] TOOL: web_search({'query': 'family-friendly activities in Tokyo for the weekend'})
  [action] → [artifact art:5d59f0dd1074cc02, 11,539 bytes] preview: ...

── iter 2 ──
[memory] 3 hits: [...]
  [perception] [done] g1: Find 3 family-friendly activities in Tokyo for the weekend  attach=art:5d59f0dd1074cc02
  [perception] [open] g2: Check Tokyo weather forecast for Saturday
  [perception] [open] g3: Recommend the most appropriate activity based on weather  attach=art:5d59f0dd1074cc02
  [decision] TOOL: web_search({'query': 'Tokyo weather forecast Saturday'})
  [action] → [artifact art:23861bcb003537f7, 10,091 bytes] preview: ...

── iter 3 ──
[memory] 4 hits: [...]
  [perception] [done] g1: Find 3 family-friendly activities in Tokyo for the weekend
  [perception] [done] g2: Check Tokyo weather forecast for Saturday  attach=art:23861bcb003537f7
  [perception] [open] g3: Recommend the most appropriate activity based on weather  attach=art:23861bcb003537f7
  [artifact] loaded art:23861bcb003537f7 (10,091 bytes)
  [decision] ANSWER: Based on the weather forecast for this coming Saturday, May 30th, in Tokyo...
[agent] all goals done

============================================================
FINAL ANSWER:
Based on the weather forecast for this coming Saturday, May 30th, in Tokyo, you can expect
pleasant conditions. The forecast indicates it will be "mainly sunny" with temperatures reaching
around 26°C (79°F) and a low probability of precipitation (around 20%).

Given this favorable weather, here are some recommended family-friendly activities:

1.  **Visit Ueno Park:** This is an excellent choice for a sunny day. The park is home to the
    Ueno Zoo, several museums (such as the Tokyo National Museum), and beautiful walking paths,
    making it perfect for a full day of family exploration.
2.  **Explore Shinjuku Gyoen National Garden:** With the sunny weather, this expansive park is
    ideal for a family picnic. It offers a mix of traditional Japanese, English, and French garden
    styles, providing plenty of space for children to run around in a serene environment.
3.  **Enjoy Odaiba:** Since it is a sunny day, you can take advantage of the waterfront area in
    Odaiba. You can visit the Miraikan (National Museum of Emerging Science and Innovation),
    enjoy the views of the Rainbow Bridge, or spend time at the beach park.
============================================================
```

---

### Query C1 — Remember Mom's Birthday (4 iterations)

**Query:** `My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.`

```
[gateway] up at http://localhost:8101

[agent:ad374c47] My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 1 hits: ["My mom's birthday is 15 May 2026. Remember that an"]
  [perception] [open] g1: Store the mom's birthday date in memory
  [perception] [open] g2: Create a calendar reminder for 1 May 2026
  [perception] [open] g3: Create a calendar reminder for 15 May 2026
  [decision] TOOL: create_file({'content': "Mom's birthday: 15 May 2026", 'path': 'mom_birthday.txt'})
  [action] → {
  "ok": true,
  "path": "mom_birthday.txt",
  "bytes": 27
}

── iter 2 ──
[memory] 5 hits: [...]
  [perception] [done] g1: Store the mom's birthday date in memory
  [perception] [open] g2: Create a calendar reminder for 1 May 2026
  [perception] [open] g3: Create a calendar reminder for 15 May 2026
  [decision] TOOL: create_file({'path': 'reminder_1_may_2026.txt', 'content': 'Calendar reminder: 1 May 2026'})
  [action] → {
  "ok": true,
  "path": "reminder_1_may_2026.txt",
  "bytes": 29
}

── iter 3 ──
[memory] 6 hits: [...]
  [perception] [done] g1: Store the mom's birthday date in memory
  [perception] [done] g2: Create a calendar reminder for 1 May 2026
  [perception] [open] g3: Create a calendar reminder for 15 May 2026
  [decision] TOOL: create_file({'content': "Calendar reminder: Mom's birthday on 15 May 2026", 'path': 'reminder_15_may_2026.txt'})
  [action] → {
  "ok": true,
  "path": "reminder_15_may_2026.txt",
  "bytes": 48
}

── iter 4 ──
[memory] 7 hits: [...]
  [perception] [done] g1: Store the mom's birthday date in memory
  [perception] [done] g2: Create a calendar reminder for 1 May 2026
  [perception] [done] g3: Create a calendar reminder for 15 May 2026
[agent] all goals done

============================================================
FINAL ANSWER:
Done: create_file → {
  "ok": true,
  "path": "reminder_15_may_2026.txt",
  "bytes": 48
}
============================================================
```

---

### Query C2 — Recall Mom's Birthday (1 iteration, memory persisted from C1)

**Query:** `When is mom's birthday?`

```
[gateway] up at http://localhost:8101

[agent:91548a0b] When is mom's birthday?
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 4 hits: ["My mom's birthday is 15 May 2026. Remember that an", 'create_file(content="Mom\'s birthday: 15 May 2026",', 'create_file(content="Calendar reminder: Mom\'s birt', "User is asking for the date of their mother's birt"]
  [perception] [open] g1: Identify mom's birthday date from memory
  [decision] ANSWER: Your mom's birthday is on May 15, 2026. I have previously saved this
    information in a file named `mom_birthday.txt` and created a calendar reminder for that date.
[agent] all goals done

============================================================
FINAL ANSWER:
Your mom's birthday is on May 15, 2026. I have previously saved this information in a file
named `mom_birthday.txt` and created a calendar reminder for that date.
============================================================
```

> **Memory persistence verified:** `--run-c2` answered in 1 iteration purely from `state/memory.json` written by `--run-c1`. No tool calls needed.

---

### Query D — Python asyncio Best Practices (3 iterations)

**Query:** `Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.`

```
[gateway] up at http://localhost:8101

[agent:7b576176] Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they
[memory] classifying query ...
[tools] 9 available: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

── iter 1 ──
[memory] 3 hits: ['Summary of common Python asyncio best practices fr', ...]
  [perception] [open] g1: Search for Python asyncio best practices
  [perception] [open] g2: Read the top 3 results
  [perception] [open] g3: Create a numbered list of common advice
  [decision] TOOL: web_search({'query': 'Python asyncio best practices'})
  [action] → [artifact art:66516270a2c6e95c, 10,229 bytes] preview: {   "title": "Asyncio best practices - Async-SIG - Discussions on Python.org", ...

── iter 2 ──
[memory] 8 hits: [...]
  [perception] [done] g1: Search for Python asyncio best practices
  [perception] [open] g2: Read the top 3 results  attach=art:66516270a2c6e95c
  [perception] [open] g3: Create a numbered list of common advice  attach=art:66516270a2c6e95c
  [artifact] loaded art:66516270a2c6e95c (10,229 bytes)
  [decision] ANSWER: Based on the provided search results, here are the key best practices...
[agent] all goals done (g2 marked done by optimization)

── iter 3 ──
[memory] 8 hits: [...]
  [perception] [done] g1: Search for Python asyncio best practices
  [perception] [done] g2: Read the top 3 results
  [perception] [open] g3: Create a numbered list of common advice  attach=art:66516270a2c6e95c
  [artifact] loaded art:66516270a2c6e95c (10,229 bytes)
  [decision] ANSWER: Based on the provided documentation and best practices...
[agent] all goals done

============================================================
FINAL ANSWER:
Based on the provided documentation and best practices for Python's `asyncio` library, here is
a list of common advice for writing efficient asynchronous code:

1.  **Never Block the Event Loop:** Avoid using synchronous, blocking calls (like `time.sleep()`
    or heavy CPU-bound operations) directly within an `async` function, as this halts the entire
    event loop. Use non-blocking alternatives like `await asyncio.sleep()` or offload blocking
    tasks to a thread pool using `loop.run_in_executor()`.
2.  **Use `asyncio.run()` as the Entry Point:** Always use `asyncio.run()` to start your main
    coroutine. This function handles the proper setup and teardown of the event loop and ensures
    that resources are cleaned up correctly when the program finishes or encounters an exception.
3.  **Create Tasks for Concurrency:** To run independent operations concurrently rather than
    sequentially, use `asyncio.create_task()` or `asyncio.gather()`. This allows the event loop
    to switch between tasks while waiting for I/O operations to complete.
4.  **Handle Cancellation Gracefully:** Always be prepared for tasks to be cancelled. Catch
    `asyncio.CancelledError` within your tasks to perform necessary cleanup of resources before
    re-raising the exception to maintain proper task state.
5.  **Prefer Async Context Managers:** When dealing with resources like network connections or
    file handles, use `async with` to ensure that resources are opened and closed correctly in
    an asynchronous-friendly manner.
6.  **Enable Debug Mode During Development:** Use `asyncio.run(main(), debug=True)` during
    development. This helps identify common issues such as never-awaited coroutines, tasks that
    block the loop, or unretrieved exceptions.
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
│   ├── .env.example       # API key template (copy to .env)
│   └── state/             # Runtime state — excluded from git
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
| Mask `art:` IDs in Decision hits | Prevents Decision from passing artifact IDs as file/URL arguments |
| Summary answer when all-done from memory | Ensures a meaningful response even when memory already has everything |
