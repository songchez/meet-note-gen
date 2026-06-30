from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .audio import TimeRange, chunk_ranges


@dataclass
class Job:
    root: Path
    state: dict

    @classmethod
    def load(cls, root: str | Path) -> "Job":
        root = Path(root)
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        return cls(root, state)

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "state.json").write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def pending_chunks(self, engine_id: str) -> list[dict]:
        done = self.state.setdefault("results", {}).setdefault(engine_id, {})
        return [chunk for chunk in self.state["chunks"] if done.get(chunk["name"]) != "done"]

    def mark_done(self, engine_id: str, chunk_name: str, text: str) -> Path:
        result_dir = self.root / "results" / engine_id
        result_dir.mkdir(parents=True, exist_ok=True)
        output_path = result_dir / f"{chunk_name}.txt"
        output_path.write_text(text, encoding="utf-8")
        self.state.setdefault("results", {}).setdefault(engine_id, {})[chunk_name] = "done"
        self.save()
        return output_path


def create_job(
    jobs_root: str | Path,
    input_path: str | Path,
    source_range: TimeRange,
    chunk_seconds: int,
    engine_ids: list[str],
) -> Job:
    root = Path(jobs_root) / f"job-{uuid4().hex[:8]}"
    chunks_dir = root / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks = [
        {
            "name": f"chunk_{index:03d}",
            "start": item.start,
            "end": item.end,
            "path": str(chunks_dir / f"chunk_{index:03d}.wav"),
        }
        for index, item in enumerate(chunk_ranges(source_range, chunk_seconds), 1)
    ]
    job = Job(
        root,
        {
            "input_path": str(input_path),
            "source_range": {"start": source_range.start, "end": source_range.end},
            "chunk_seconds": chunk_seconds,
            "engine_ids": engine_ids,
            "chunks": chunks,
            "results": {engine_id: {} for engine_id in engine_ids},
        },
    )
    job.save()
    return job
