from __future__ import annotations

from datetime import datetime
from pathlib import Path


def next_recording_path(app_root: str | Path, now: datetime | None = None) -> Path:
    folder = Path(app_root) / "recordings"
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    candidate = folder / f"recording-{stamp}.m4a"
    index = 2
    while candidate.exists():
        candidate = folder / f"recording-{stamp}-{index:02d}.m4a"
        index += 1
    return candidate
