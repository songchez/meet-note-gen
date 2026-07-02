from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model_catalog import catalog_entries

ENGINE_NAMES = {entry.engine_id: entry.name for entry in catalog_entries()}
ENGINE_HOME_PAGES = {entry.engine_id: entry.download_url for entry in catalog_entries()}
RUNNER_SUFFIXES = {".exe", ".cmd", ".bat"}


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
        return EngineStatus(False, f"Unknown engine: {config.engine_id}")
    if _path_is_empty(config.executable) or not config.executable.is_file():
        return EngineStatus(False, "Choose runner file")
    if config.executable.suffix.lower() not in RUNNER_SUFFIXES:
        return EngineStatus(False, "Choose Windows runner (.exe)")
    if _path_is_empty(config.model_path) or not config.model_path.exists():
        return EngineStatus(False, "Choose model path")
    return EngineStatus(True, "Ready")


def _path_is_empty(path: Path) -> bool:
    return str(path) in ("", ".")


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
        model_file = _sensevoice_model_file(config.model_path)
        return [
            str(config.executable),
            f"--tokens={config.model_path / 'tokens.txt'}",
            f"--sense-voice-model={model_file}",
            "--num-threads=2",
            "--sense-voice-language=ko",
            "--sense-voice-use-itn=1",
            "--debug=0",
            str(audio_path),
        ]
    raise ValueError(f"unknown engine: {config.engine_id}")


def _sensevoice_model_file(model_path: Path) -> Path:
    int8_model = model_path / "model.int8.onnx"
    if int8_model.exists():
        return int8_model
    fp32_model = model_path / "model.onnx"
    if fp32_model.exists():
        return fp32_model
    return int8_model
