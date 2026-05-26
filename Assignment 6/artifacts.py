"""
artifacts.py
Content-addressed store for large tool results (>= 4 KB).
Handles are "art:<sha256-prefix>". Storage is two files per artifact:
  state/artifacts/<hash>.bin  — raw bytes
  state/artifacts/<hash>.json — Artifact metadata
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from schemas import Artifact

_DEFAULT_DIR = Path(__file__).parent / "state" / "artifacts"


class ArtifactStore:
    def __init__(self, base: Path = _DEFAULT_DIR) -> None:
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)

    def _hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]

    def put(self, blob: bytes, *, content_type: str, source: str, descriptor: str) -> str:
        h = self._hash(blob)
        art_id = f"art:{h}"
        bin_path = self._base / f"{h}.bin"
        meta_path = self._base / f"{h}.json"
        if not bin_path.exists():
            bin_path.write_bytes(blob)
            meta = Artifact(
                id=art_id, content_type=content_type,
                size_bytes=len(blob), source=source, descriptor=descriptor,
            )
            meta_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        return art_id

    def get_bytes(self, artifact_id: str) -> bytes:
        h = artifact_id.removeprefix("art:")
        return (self._base / f"{h}.bin").read_bytes()

    def get_meta(self, artifact_id: str) -> Artifact:
        h = artifact_id.removeprefix("art:")
        return Artifact.model_validate_json(
            (self._base / f"{h}.json").read_text(encoding="utf-8")
        )

    def exists(self, artifact_id: str) -> bool:
        if not artifact_id or not artifact_id.startswith("art:"):
            return False
        h = artifact_id.removeprefix("art:")
        return (self._base / f"{h}.bin").exists()


artifacts = ArtifactStore()
