from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .audio import TimeRange, build_chunk_commands


TWENTY_MINUTES_SECONDS = 20 * 60


@dataclass(frozen=True)
class SplitZipPlan:
    work_dir: Path
    chunks_dir: Path
    zip_path: Path
    commands: list[list[str]]
    chunk_paths: list[Path]


def build_split_zip_plan(input_path: Path, output_root: Path, source_range: TimeRange, now: datetime | None = None) -> SplitZipPlan:
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    name = f"{input_path.stem}-20min-chunks-{timestamp}"
    work_dir = output_root / name
    chunks_dir = work_dir / "chunks"
    zip_path = output_root / f"{name}.zip"
    commands = build_chunk_commands(input_path, chunks_dir, source_range, TWENTY_MINUTES_SECONDS)
    return SplitZipPlan(work_dir, chunks_dir, zip_path, commands, [Path(command[-1]) for command in commands])


def create_zip_archive(zip_path: Path, files: list[Path]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return zip_path
