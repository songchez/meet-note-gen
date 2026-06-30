# Meet Note Gen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Windows Python desktop MVP for long-audio trimming, chunking, model-path management, and external ASR engine execution.

**Architecture:** Keep the desktop GUI thin and put all durable behavior in small stdlib-friendly core modules. Audio preparation is ffmpeg command generation plus subprocess execution. ASR engines are external CLI adapters for Qwen3-ASR, SenseVoice/sherpa-onnx, and Whisper.cpp.

**Tech Stack:** Python 3.10+, PySide6, pyqtgraph, stdlib unittest, ffmpeg, external ASR executables.

---

## File Structure

- Create: `pyproject.toml` - package metadata, dependencies, test config.
- Create: `README.md` - local run instructions and model-install flow.
- Create: `src/meet_note_gen/__init__.py` - package marker.
- Create: `src/meet_note_gen/__main__.py` - `python -m meet_note_gen` entry point.
- Create: `src/meet_note_gen/paths.py` - Windows app data paths, with env override for tests.
- Create: `src/meet_note_gen/audio.py` - time range validation, even splits, ffmpeg command builders.
- Create: `src/meet_note_gen/engines.py` - engine config, validation, and CLI command builders.
- Create: `src/meet_note_gen/jobs.py` - job folders, chunk state, result paths, resume helpers.
- Create: `src/meet_note_gen/gui.py` - PySide6 desktop shell, model manager table, basic controls.
- Create: `tests/test_audio.py` - split/trim/ffmpeg command checks.
- Create: `tests/test_engines.py` - engine validation and command builder checks.
- Create: `tests/test_jobs.py` - job state and resume checks.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/meet_note_gen/__init__.py`
- Create: `src/meet_note_gen/__main__.py`
- Create: `src/meet_note_gen/paths.py`

- [ ] **Step 1: Write package metadata**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "meet-note-gen"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "PySide6>=6.7",
  "pyqtgraph>=0.13",
  "numpy>=1.26",
]

[project.scripts]
meet-note-gen = "meet_note_gen.__main__:main"
```

- [ ] **Step 2: Add path helpers**

```python
from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "MeetNoteGen"


def app_dir() -> Path:
    override = os.environ.get("MEET_NOTE_GEN_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME


def ensure_app_dirs() -> Path:
    root = app_dir()
    for name in ("engines", "models", "jobs", "output"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root
```

- [ ] **Step 3: Add entry point**

```python
from __future__ import annotations

from .gui import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run scaffold import check**

Run: `python -m compileall src`

Expected: all created modules compile.

## Task 2: Audio Math and ffmpeg Commands

**Files:**
- Create: `src/meet_note_gen/audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write failing tests**

```python
from meet_note_gen.audio import TimeRange, build_chunk_commands, split_evenly


def test_split_evenly_covers_duration_without_overlap():
    assert split_evenly(100.0, 3) == [
        TimeRange(0.0, 33.333),
        TimeRange(33.333, 66.667),
        TimeRange(66.667, 100.0),
    ]


def test_invalid_range_rejected():
    try:
        TimeRange(10, 5).validate(100)
    except ValueError as exc:
        assert "start must be before end" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_ffmpeg_chunk_command_uses_16k_mono(tmp_path):
    commands = build_chunk_commands("in.mp3", tmp_path, TimeRange(0, 1200), 600)
    assert len(commands) == 2
    assert commands[0][:4] == ["ffmpeg", "-y", "-ss", "0.000"]
    assert commands[0][-6:] == ["-ac", "1", "-ar", "16000", str(tmp_path / "chunk_001.wav")]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_audio -v`

Expected: import failure because `meet_note_gen.audio` does not exist.

- [ ] **Step 3: Implement minimal audio module**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimeRange:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def validate(self, total_duration: float) -> "TimeRange":
        if self.start < 0:
            raise ValueError("start must be non-negative")
        if self.end > total_duration:
            raise ValueError("end must be within audio duration")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


def split_evenly(duration: float, parts: int) -> list[TimeRange]:
    if duration <= 0:
        raise ValueError("duration must be positive")
    if parts < 2:
        raise ValueError("parts must be at least 2")
    ranges: list[TimeRange] = []
    for index in range(parts):
        start = round(duration * index / parts, 3)
        end = round(duration * (index + 1) / parts, 3)
        ranges.append(TimeRange(start, end))
    return ranges


def chunk_ranges(source_range: TimeRange, chunk_seconds: int) -> list[TimeRange]:
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")
    ranges: list[TimeRange] = []
    start = source_range.start
    while start < source_range.end:
        end = min(start + chunk_seconds, source_range.end)
        ranges.append(TimeRange(round(start, 3), round(end, 3)))
        start = end
    return ranges


def build_chunk_commands(
    input_path: str | Path,
    output_dir: str | Path,
    source_range: TimeRange,
    chunk_seconds: int,
) -> list[list[str]]:
    output_dir = Path(output_dir)
    commands = []
    for index, item in enumerate(chunk_ranges(source_range, chunk_seconds), 1):
        commands.append([
            "ffmpeg",
            "-y",
            "-ss",
            f"{item.start:.3f}",
            "-t",
            f"{item.duration:.3f}",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_dir / f"chunk_{index:03d}.wav"),
        ])
    return commands
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_audio -v`

Expected: 3 passed.

## Task 3: Job State and Resume

**Files:**
- Create: `src/meet_note_gen/jobs.py`
- Create: `tests/test_jobs.py`

- [ ] **Step 1: Write failing tests**

```python
import json

from meet_note_gen.audio import TimeRange
from meet_note_gen.jobs import Job, create_job


def test_create_job_writes_state(tmp_path):
    job = create_job(tmp_path, "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
    state = json.loads((job.root / "state.json").read_text(encoding="utf-8"))
    assert state["input_path"] == "meeting.mp3"
    assert state["chunks"][0]["name"] == "chunk_001"


def test_pending_chunks_skip_completed(tmp_path):
    job = create_job(tmp_path, "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
    job.mark_done("qwen3", "chunk_001", "hello")
    loaded = Job.load(job.root)
    assert [chunk["name"] for chunk in loaded.pending_chunks("qwen3")] == ["chunk_002"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_jobs -v`

Expected: import failure because `meet_note_gen.jobs` does not exist.

- [ ] **Step 3: Implement minimal job module**

Use JSON state so partial results survive process exit. Store chunk text under `results/<engine>/<chunk>.txt`.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_jobs -v`

Expected: 2 passed.

## Task 4: Engine Registry and Commands

**Files:**
- Create: `src/meet_note_gen/engines.py`
- Create: `tests/test_engines.py`

- [ ] **Step 1: Write failing tests**

```python
from meet_note_gen.engines import EngineConfig, build_command, validate_engine


def test_missing_executable_is_invalid(tmp_path):
    config = EngineConfig("qwen3", tmp_path / "missing.exe", tmp_path / "model")
    status = validate_engine(config)
    assert not status.ok
    assert "executable missing" in status.message


def test_whisper_command_contains_model_and_output(tmp_path):
    exe = tmp_path / "whisper-cli.exe"
    model = tmp_path / "ggml-large-v3-turbo-q5_0.bin"
    audio = tmp_path / "chunk_001.wav"
    out = tmp_path / "chunk_001"
    exe.write_text("", encoding="utf-8")
    model.write_text("", encoding="utf-8")
    audio.write_text("", encoding="utf-8")
    command = build_command(EngineConfig("whisper", exe, model), audio, out)
    assert command[:3] == [str(exe), "-m", str(model)]
    assert "-l" in command
    assert "ko" in command
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_engines -v`

Expected: import failure because `meet_note_gen.engines` does not exist.

- [ ] **Step 3: Implement engine command builders**

Implement three IDs: `qwen3`, `sensevoice`, `whisper`. Build commands only; do not execute them in this module.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_engines -v`

Expected: 2 passed.

## Task 5: GUI Shell

**Files:**
- Create: `src/meet_note_gen/gui.py`
- Modify: `src/meet_note_gen/__main__.py`

- [ ] **Step 1: Add a thin PySide6 shell**

Create a main window with:

- Open button.
- Play/stop buttons disabled until playback is wired.
- Model dropdown with Qwen3, SenseVoice, Whisper.
- Engine table with status, Install, and Folder buttons.
- Chunk size dropdown.
- Transcribe and Compare Models buttons.
- Log panel.

- [ ] **Step 2: Keep GUI imports out of core tests**

`__main__.py` imports `gui.run`, but core modules do not import PySide6.

- [ ] **Step 3: Compile check**

Run: `python -m compileall src`

Expected: all modules compile. If PySide6 is not installed in the current environment, do not run the GUI here.

## Task 6: Engine Execution and Result Writing

**Files:**
- Create: `src/meet_note_gen/runner.py`
- Modify: `src/meet_note_gen/jobs.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write failing test with fake command**

```python
import sys

from meet_note_gen.runner import run_command


def test_run_command_captures_stdout(tmp_path):
    output = run_command([sys.executable, "-c", "print('hello')"], tmp_path)
    assert output.stdout.strip() == "hello"
    assert output.returncode == 0
```

- [ ] **Step 2: Implement subprocess wrapper**

Use `subprocess.run(..., capture_output=True, text=True, cwd=...)`. Return stdout, stderr, and return code.

- [ ] **Step 3: Run test**

Run: `PYTHONPATH=src python3 -m unittest tests.test_runner -v`

Expected: 1 passed.

## Task 7: Documentation and Smoke Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document local setup**

Include:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m meet_note_gen
```

- [ ] **Step 2: Document external requirements**

List:

- ffmpeg must be installed or available in PATH.
- Qwen3-ASR runner path is selected in the app.
- sherpa-onnx/SenseVoice path is selected in the app.
- whisper.cpp `whisper-cli.exe` and `large-v3-turbo-q5` model path are selected in the app.

- [ ] **Step 3: Run all checks**

Run:

```bash
python -m compileall src
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: compile succeeds and tests pass.

## Self-Review

- Spec coverage: The plan covers desktop app scaffold, model-install path management, ffmpeg command generation, chunk planning, resumable jobs, three engine adapters, and basic GUI.
- Deferred by design: automatic model download, real waveform rendering, real playback, and actual ASR engine smoke tests on Windows hardware. These require local Windows engine binaries and sample audio.
- Placeholder scan: no placeholder entries are used as implementation requirements.
- Type consistency: `TimeRange`, `EngineConfig`, `Job`, and `run_command` are introduced before dependent tasks use them.
