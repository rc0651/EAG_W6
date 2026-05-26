"""
tools.py
9 MCP tools exposed via stdio transport.

web_search  — Tavily primary, DuckDuckGo fallback, max 5 results
fetch_url   — crawl4ai headless Chromium → clean markdown
get_time    — current time in any IANA timezone
currency_convert — live FX via frankfurter.dev
read_file / list_dir / create_file / update_file / edit_file — sandboxed to ./workspace/
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from ddgs import DDGS
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

MAX_RESULTS = 5
mcp = FastMCP("cognitive-agent-tools")

WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)

_USAGE_FILE = Path(__file__).parent / "usage.json"
_MONTHLY_LIMIT = 950
_lock = threading.Lock()


def _bounded(path: str) -> Path:
    resolved = (WORKSPACE / path).resolve()
    if resolved != WORKSPACE.resolve() and WORKSPACE.resolve() not in resolved.parents:
        raise ValueError(f"'{path}' is outside the workspace sandbox")
    return resolved


def _usage_now() -> dict:
    month = datetime.now().strftime("%Y-%m")
    if not _USAGE_FILE.exists():
        return {"month": month, "tavily": {"n": 0, "err": 0}, "ddg": {"n": 0, "err": 0}}
    try:
        d = json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"month": month, "tavily": {"n": 0, "err": 0}, "ddg": {"n": 0, "err": 0}}
    if d.get("month") != month:
        return {"month": month, "tavily": {"n": 0, "err": 0}, "ddg": {"n": 0, "err": 0}}
    return d


def _save_usage(d: dict) -> None:
    _USAGE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _tick(provider: str, field: str = "n") -> None:
    with _lock:
        d = _usage_now()
        d[provider][field] = d[provider].get(field, 0) + 1
        _save_usage(d)


def _within_limit(provider: str) -> bool:
    return _usage_now()[provider]["n"] < _MONTHLY_LIMIT


def _tavily(query: str, n: int) -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(os.environ["TAVILY_API_KEY"])
    resp = client.search(query=query, max_results=n, search_depth="advanced")
    return [{"title": r.get("title",""), "url": r.get("url",""), "snippet": r.get("content","")}
            for r in resp.get("results", [])]


def _ddg(query: str, n: int) -> list[dict]:
    hits: list[dict] = []
    with DDGS() as d:
        for backend in ("auto", "html", "lite"):
            try:
                hits = list(d.text(query, max_results=n, backend=backend))
            except Exception:
                hits = []
            if hits:
                break
    return [{"title": h.get("title",""), "url": h.get("href",""), "snippet": h.get("body","")}
            for h in hits]


async def _crawl(url: str) -> dict:
    from crawl4ai import AsyncWebCrawler
    saved = os.dup(1)
    os.dup2(2, 1)
    try:
        async with AsyncWebCrawler(verbose=False) as c:
            r = await c.arun(url=url)
    finally:
        os.dup2(saved, 1)
        os.close(saved)
    md = r.markdown
    raw = (getattr(md, "raw_markdown", None)
           or getattr(md, "fit_markdown", None)
           or md or r.cleaned_html or r.html or "")
    text = str(raw)
    return {
        "status": int(getattr(r, "status_code", None) or 200),
        "mime": "text/markdown",
        "bytes": len(text.encode("utf-8")),
        "text": text,
    }


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web. Tavily primary, DuckDuckGo fallback. Max 5 results."""
    n = max(1, min(max_results, MAX_RESULTS))
    if os.environ.get("TAVILY_API_KEY") and _within_limit("tavily"):
        try:
            out = _tavily(query, n)
            if out:
                _tick("tavily")
                return out
        except Exception:
            _tick("tavily", "err")
    out = _ddg(query, n)
    _tick("ddg")
    return out


@mcp.tool()
async def fetch_url(url: str, timeout: int = 20) -> dict:
    """Fetch a URL and return clean markdown via headless Chromium (crawl4ai)."""
    return await _crawl(url)


@mcp.tool()
def get_time(timezone: str = "UTC") -> dict:
    """Return current time in the given IANA timezone. Example: get_time('Asia/Kolkata')."""
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    offset = now.utcoffset()
    return {
        "iso": now.isoformat(),
        "human": now.strftime("%A, %d %B %Y %H:%M:%S %Z"),
        "timezone": timezone,
        "offset_hours": offset.total_seconds() / 3600 if offset else 0.0,
    }


@mcp.tool()
def currency_convert(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert between currencies using live rates from frankfurter.dev."""
    f, t = from_currency.upper(), to_currency.upper()
    url = f"https://api.frankfurter.dev/v1/latest?amount={amount}&base={f}&symbols={t}"
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    converted = data["rates"][t]
    return {"amount": amount, "from": f, "to": t,
            "rate": converted / amount if amount else 0.0,
            "converted": converted, "date": data["date"]}


@mcp.tool()
def read_file(path: str) -> dict:
    """Read a file from the workspace sandbox."""
    p = _bounded(path)
    text = p.read_text(encoding="utf-8")
    return {"path": path, "bytes": p.stat().st_size, "content": text}


@mcp.tool()
def list_dir(path: str = ".") -> list[dict]:
    """List contents of a workspace directory."""
    p = _bounded(path)
    return [{"name": c.name, "type": "dir" if c.is_dir() else "file",
             "bytes": 0 if c.is_dir() else c.stat().st_size}
            for c in sorted(p.iterdir())]


@mcp.tool()
def create_file(path: str, content: str) -> dict:
    """Create a new file in the workspace. Fails if it already exists."""
    p = _bounded(path)
    if p.exists():
        raise ValueError(f"'{path}' already exists")
    if not p.parent.exists():
        raise ValueError(f"Parent dir of '{path}' does not exist")
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "bytes": p.stat().st_size}


@mcp.tool()
def update_file(path: str, content: str) -> dict:
    """Overwrite an existing workspace file."""
    p = _bounded(path)
    if not p.exists():
        raise ValueError(f"'{path}' does not exist")
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "bytes": p.stat().st_size}


@mcp.tool()
def edit_file(path: str, find: str, replace: str, replace_all: bool = False) -> dict:
    """Find-and-replace within a workspace file."""
    p = _bounded(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(find)
    if count == 0:
        raise ValueError(f"'{find}' not found in '{path}'")
    if count > 1 and not replace_all:
        raise ValueError(f"'{find}' occurs {count} times — pass replace_all=True")
    new_text = text.replace(find, replace) if replace_all else text.replace(find, replace, 1)
    p.write_text(new_text, encoding="utf-8")
    return {"ok": True, "path": path, "replacements": count if replace_all else 1,
            "bytes": p.stat().st_size}


if __name__ == "__main__":
    mcp.run(transport="stdio")
