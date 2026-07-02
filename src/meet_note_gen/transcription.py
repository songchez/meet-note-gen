from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .audio import TimeRange, build_chunk_commands
from .engines import EngineConfig, build_command, validate_engine
from .jobs import Job
from .runner import CommandResult, run_command


RunCommand = Callable[[list[str], str | Path], CommandResult]
ShouldStop = Callable[[], bool]
Log = Callable[[str], None]


def transcribe_job(
    job: Job,
    config: EngineConfig,
    run: RunCommand = run_command,
    prepare_chunks: bool = True,
    should_stop: ShouldStop = lambda: False,
    on_log: Log = lambda message: None,
) -> Path:
    status = validate_engine(config)
    if not status.ok:
        raise ValueError(status.message)
    if prepare_chunks:
        _prepare_chunks(job, run, should_stop, on_log)
    engine_id = config.engine_id
    for chunk in job.pending_chunks(engine_id):
        if should_stop():
            raise RuntimeError("Job stopped")
        on_log(f"{engine_id}: transcribing {chunk['name']}")
        output_stem = job.root / "results" / engine_id / chunk["name"]
        output_stem.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = run(build_command(config, chunk["path"], output_stem), job.root)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 193:
                raise RuntimeError("Windows runner 파일이 아닙니다. 모델 설정에서 .exe runner를 다시 선택하세요.") from exc
            raise
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"{engine_id} failed on {chunk['name']}")
        job.mark_done(engine_id, chunk["name"], _read_engine_text(output_stem, result, engine_id))
    output = merge_transcript(job, engine_id)
    on_log(f"{engine_id}: wrote {output}")
    return output


def merge_transcript(job: Job, engine_id: str) -> Path:
    result_dir = job.root / "results" / engine_id
    chunks = []
    for chunk in job.state["chunks"]:
        path = result_dir / f"{chunk['name']}.txt"
        if path.exists():
            chunks.append(
                {
                    "engine": engine_id,
                    "chunk": chunk["name"],
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "text": path.read_text(encoding="utf-8").strip(),
                }
            )
    output = result_dir / "transcript.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(chunk["text"] for chunk in chunks).strip() + ("\n" if chunks else ""), encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps({"engine": engine_id, "chunks": chunks}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def _prepare_chunks(job: Job, run: RunCommand, should_stop: ShouldStop, on_log: Log) -> None:
    state = job.state
    source = TimeRange(state["source_range"]["start"], state["source_range"]["end"])
    commands = build_chunk_commands(state["input_path"], job.root / "chunks", source, state["chunk_seconds"])
    for command in commands:
        if should_stop():
            raise RuntimeError("Job stopped")
        output = Path(command[-1])
        if output.exists():
            continue
        on_log(f"ffmpeg: creating {output.name}")
        output.parent.mkdir(parents=True, exist_ok=True)
        result = run(command, job.root)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"ffmpeg failed on {output.name}")


def _read_engine_text(output_stem: Path, result: CommandResult, engine_id: str) -> str:
    txt = output_stem.with_suffix(".txt")
    if txt.exists():
        return txt.read_text(encoding="utf-8")
    if engine_id == "sensevoice":
        text = _extract_json_text(result.stdout)
        if text:
            return text
    return result.stdout


def _extract_json_text(stdout: str) -> str:
    chunks = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks)
