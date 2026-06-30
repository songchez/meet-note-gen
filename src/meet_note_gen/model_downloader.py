from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .model_catalog import ModelCatalogEntry


DownloadFn = Callable[..., str]


def download_model(
    app_root: str | Path,
    entry: ModelCatalogEntry,
    snapshot_download: DownloadFn | None = None,
    hf_hub_download: DownloadFn | None = None,
) -> Path:
    target = Path(app_root) / "models" / entry.local_dir
    target.mkdir(parents=True, exist_ok=True)
    if entry.hf_filename:
        download = hf_hub_download or _hf_hub_download
        return Path(download(repo_id=entry.hf_repo_id, filename=entry.hf_filename, local_dir=str(target)))
    download = snapshot_download or _snapshot_download
    return Path(download(repo_id=entry.hf_repo_id, local_dir=str(target)))


def _snapshot_download(**kwargs: Any) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def _hf_hub_download(**kwargs: Any) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(**kwargs)
