from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ENGINE_NAMES = {
    "qwen3": "Qwen3-ASR 0.6B",
    "sensevoice": "SenseVoiceSmall INT8",
    "whisper": "Whisper large-v3-turbo Q5",
}


@dataclass(frozen=True)
class EngineConfig:
    engine_id: str
    executable: Path
    model_path: Path


@dataclass(frozen=True)
class EngineStatus:
    ok: bool
    message: str


def validate_engine(config: EngineConfig) -> EngineStatus:
    if config.engine_id not in ENGINE_NAMES:
        return EngineStatus(False, f"unknown engine: {config.engine_id}")
    if not config.executable.exists():
        return EngineStatus(False, "executable missing")
    if not config.model_path.exists():
        return EngineStatus(False, "model path missing")
    return EngineStatus(True, "ready")


def build_command(config: EngineConfig, audio_path: str | Path, output_stem: str | Path) -> list[str]:
    audio_path = Path(audio_path)
    output_stem = Path(output_stem)
    if config.engine_id == "whisper":
        return [
            str(config.executable),
            "-m",
            str(config.model_path),
            "-f",
            str(audio_path),
            "-l",
            "ko",
            "-otxt",
            "-oj",
            "-of",
            str(output_stem),
        ]
    if config.engine_id == "qwen3":
        return [
            str(config.executable),
            "-d",
            str(config.model_path),
            "-i",
            str(audio_path),
            "--language",
            "Korean",
            "-o",
            str(output_stem.with_suffix(".txt")),
        ]
    if config.engine_id == "sensevoice":
        return [
            str(config.executable),
            "--model",
            str(config.model_path),
            "--tokens",
            str(config.model_path / "tokens.txt"),
            str(audio_path),
            str(output_stem.with_suffix(".txt")),
        ]
    raise ValueError(f"unknown engine: {config.engine_id}")
