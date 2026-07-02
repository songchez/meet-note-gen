from __future__ import annotations

import fnmatch
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
from typing import Any

from .model_catalog import ModelCatalogEntry


DownloadFn = Callable[..., str]
ReleaseFetchFn = Callable[[str], dict[str, Any]]
FileDownloadFn = Callable[[str, Path], None]


@dataclass(frozen=True)
class InstalledAssets:
    model_path: Path
    runner_path: Path | None


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


def install_engine_assets(
    app_root: str | Path,
    entry: ModelCatalogEntry,
    snapshot_download: DownloadFn | None = None,
    hf_hub_download: DownloadFn | None = None,
    release_fetcher: ReleaseFetchFn | None = None,
    file_downloader: FileDownloadFn | None = None,
) -> InstalledAssets:
    model_path = download_model(app_root, entry, snapshot_download=snapshot_download, hf_hub_download=hf_hub_download)
    runner_path = download_runner(app_root, entry, release_fetcher=release_fetcher, file_downloader=file_downloader)
    return InstalledAssets(model_path, runner_path)


def download_runner(
    app_root: str | Path,
    entry: ModelCatalogEntry,
    release_fetcher: ReleaseFetchFn | None = None,
    file_downloader: FileDownloadFn | None = None,
) -> Path | None:
    if not entry.runner_repo:
        return None
    release = (release_fetcher or _github_latest_release)(entry.runner_repo)
    asset = select_runner_asset(release, entry.runner_asset_pattern)
    target = Path(app_root) / "engines" / entry.engine_id / asset["name"]
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    (file_downloader or _download_file)(asset["browser_download_url"], target)
    return target


def select_runner_asset(release: dict[str, Any], pattern: str) -> dict[str, str]:
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if fnmatch.fnmatchcase(name, pattern) and url:
            return {"name": name, "browser_download_url": url}
    raise RuntimeError(f"Runner asset not found: {pattern}")


def _snapshot_download(**kwargs: Any) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def _hf_hub_download(**kwargs: Any) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(**kwargs)


def _github_latest_release(repo: str) -> dict[str, Any]:
    request = Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "meet-note-gen"},
    )
    with urlopen(request) as response:  # noqa: S310 - fixed GitHub API endpoint from catalog metadata.
        return json.loads(response.read().decode("utf-8"))


def _download_file(url: str, target: Path) -> None:
    temp = target.with_suffix(target.suffix + ".tmp")
    request = Request(url, headers={"User-Agent": "meet-note-gen"})
    with urlopen(request) as response, temp.open("wb") as file:  # noqa: S310 - URL comes from GitHub release API.
        shutil.copyfileobj(response, file)
    temp.replace(target)
