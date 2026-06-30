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
    return [
        TimeRange(round(duration * index / parts, 3), round(duration * (index + 1) / parts, 3))
        for index in range(parts)
    ]


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
    return [
        [
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
        ]
        for index, item in enumerate(chunk_ranges(source_range, chunk_seconds), 1)
    ]


def build_waveform_image_command(
    input_path: str | Path,
    output_path: str | Path,
    width: int = 1600,
    height: int = 220,
) -> list[str]:
    if width <= 0 or height <= 0:
        raise ValueError("waveform dimensions must be positive")
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-filter_complex",
        f"aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors=#4c78a8",
        "-frames:v",
        "1",
        str(output_path),
    ]
