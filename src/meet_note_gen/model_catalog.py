from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCatalogEntry:
    engine_id: str
    name: str
    summary: str
    download_url: str
    hf_repo_id: str
    local_dir: str
    runner_label: str
    model_label: str
    hf_filename: str = ""
    recommended: bool = False


MODEL_CATALOG = (
    ModelCatalogEntry(
        "sensevoice",
        "SenseVoiceSmall INT8",
        "가벼운 빠른 변환 / 자동 설치 우선",
        "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-funasr-nano-int8-2025-12-17",
        "csukuangfj/sherpa-onnx-sense-voice-funasr-nano-int8-2025-12-17",
        "sensevoice-small-int8",
        "Runner 파일",
        "모델 폴더",
        recommended=True,
    ),
    ModelCatalogEntry(
        "qwen3",
        "Qwen3-ASR 0.6B",
        "한국어 회의 고급 설정",
        "https://huggingface.co/Qwen/Qwen3-ASR-0.6B",
        "Qwen/Qwen3-ASR-0.6B",
        "qwen3-asr-0.6b",
        "Runner 파일",
        "모델 폴더",
    ),
    ModelCatalogEntry(
        "whisper",
        "Whisper large-v3-turbo Q5",
        "안정적인 fallback",
        "https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-large-v3-turbo-q5_0.bin",
        "ggerganov/whisper.cpp",
        "whisper-large-v3-turbo-q5",
        "whisper-cli.exe",
        "모델 파일",
        "ggml-large-v3-turbo-q5_0.bin",
    ),
)


def catalog_entries() -> tuple[ModelCatalogEntry, ...]:
    return MODEL_CATALOG


def catalog_by_engine() -> dict[str, ModelCatalogEntry]:
    return {entry.engine_id: entry for entry in MODEL_CATALOG}


def default_engine_id() -> str:
    return MODEL_CATALOG[0].engine_id
