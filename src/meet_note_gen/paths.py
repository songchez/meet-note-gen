from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "MeetNoteGen"


def app_dir() -> Path:
    override = os.environ.get("MEET_NOTE_GEN_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME


def ensure_app_dirs() -> Path:
    root = app_dir()
    for name in ("engines", "models", "jobs", "output"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root
