"""
action.py
Action role — pure MCP dispatch. No LLM.

Returns tuple[str, str | None]: (result_descriptor, artifact_id_or_None)

Two guards:
  1. Rejects art: refs passed as tool arguments.
  2. Payloads >= 4 KB are stored as artifacts; loop gets a short descriptor + art: id.
"""
from __future__ import annotations

from mcp import ClientSession

from artifacts import ArtifactStore
from schemas import ToolCall

ARTIFACT_THRESHOLD_BYTES = 4096


async def execute(
    session: ClientSession,
    tool_call: ToolCall,
    store: ArtifactStore,
) -> tuple[str, str | None]:
    """Dispatch one MCP tool call. Returns (descriptor, artifact_id_or_None)."""

    # Guard: reject art: handles as tool arguments
    for k, v in tool_call.arguments.items():
        if isinstance(v, str) and v.startswith("art:"):
            return (
                f"[ERROR] argument '{k}' is an artifact ID '{v}'. "
                "Artifact IDs are not file paths or URLs. "
                "Read content from ATTACHED ARTIFACTS in the Decision context.",
                None,
            )

    try:
        result = await session.call_tool(tool_call.name, arguments=tool_call.arguments)
    except Exception as e:
        return f"[ERROR] tool '{tool_call.name}' failed: {e}", None

    parts: list[str] = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict):
            parts.append(block.get("text", str(block)))
        else:
            parts.append(str(block))

    raw = "\n".join(parts)
    raw_bytes = raw.encode("utf-8")

    if len(raw_bytes) >= ARTIFACT_THRESHOLD_BYTES:
        art_id = store.put(
            raw_bytes,
            content_type="text/plain",
            source=f"{tool_call.name}({list(tool_call.arguments.values())[:1]})",
            descriptor=f"{tool_call.name} result — {len(raw_bytes):,} bytes",
        )
        preview = raw[:300].replace("\n", " ")
        return (
            f"[artifact {art_id}, {len(raw_bytes):,} bytes] preview: {preview}",
            art_id,
        )

    return raw[:2000], None
