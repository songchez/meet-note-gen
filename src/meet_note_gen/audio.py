from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


UI_ROUNDING_TOLERANCE_SECONDS = 0.1


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


def build_extract_command(input_path: str | Path, output_path: str | Path, source_range: TimeRange) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-ss",
        f"{source_range.start:.3f}",
        "-t",
        f"{source_range.duration:.3f}",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]


def build_export_segment_commands(
    input_path: str | Path,
    output_dir: str | Path,
    source_range: TimeRange,
    parts: int,
) -> list[list[str]]:
    output_dir = Path(output_dir)
    return [
        build_extract_command(input_path, output_dir / f"segment_{index:03d}.wav", item)
        for index, item in enumerate(_offset_ranges(source_range, parts), 1)
    ]


def _offset_ranges(source_range: TimeRange, parts: int) -> list[TimeRange]:
    if parts == 1:
        return [source_range]
    return [
        TimeRange(round(source_range.start + item.start, 3), round(source_range.start + item.end, 3))
        for item in split_evenly(source_range.duration, parts)
    ]


def build_ffprobe_duration_command(input_path: str | Path) -> list[str]:
    return [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]


def parse_duration(output: str) -> float:
    try:
        duration = float(output.strip())
    except ValueError as exc:
        raise ValueError("Could not read audio duration") from exc
    if duration <= 0:
        raise ValueError("Could not read audio duration")
    return round(duration, 3)


def selected_range(
    total_duration: float,
    start_seconds: float = 0,
    end_seconds: float = 0,
    cut_last_seconds: float = 0,
) -> TimeRange:
    end = end_seconds if end_seconds > 0 else total_duration
    if cut_last_seconds > 0:
        end = min(end, total_duration - cut_last_seconds)
    if total_duration < end <= total_duration + UI_ROUNDING_TOLERANCE_SECONDS:
        end = total_duration
    return TimeRange(round(start_seconds, 3), round(end, 3)).validate(total_duration)


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
