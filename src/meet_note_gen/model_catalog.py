from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCatalogEntry:
    engine_id: str
    name: str
    summary: str
    download_url: str
    runner_label: str
    model_label: str
    recommended: bool = False


MODEL_CATALOG = (
    ModelCatalogEntry(
        "qwen3",
        "Qwen3-ASR 0.6B",
        "한국어 회의 추천",
        "https://github.com/antirez/qwen-asr",
        "Runner 파일",
        "모델 폴더",
        True,
    ),
    ModelCatalogEntry(
        "sensevoice",
        "SenseVoiceSmall INT8",
        "가벼운 빠른 변환",
        "https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html",
        "Runner 파일",
        "모델 폴더",
    ),
    ModelCatalogEntry(
        "whisper",
        "Whisper large-v3-turbo Q5",
        "안정적인 fallback",
        "https://github.com/ggml-org/whisper.cpp",
        "whisper-cli.exe",
        "모델 파일",
    ),
)


def catalog_entries() -> tuple[ModelCatalogEntry, ...]:
    return MODEL_CATALOG


def catalog_by_engine() -> dict[str, ModelCatalogEntry]:
    return {entry.engine_id: entry for entry in MODEL_CATALOG}
