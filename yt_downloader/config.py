"""Persistent defaults for the ytdl command."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Settings:
    download_dir: str = "downloads"
    quality: Literal["best", "compatible"] = "best"
    keep_video: bool = False

    @classmethod
    def from_dict(cls, data: object) -> Settings:
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object.")
        unknown = set(data) - {"download_dir", "quality", "keep_video"}
        if unknown:
            raise ValueError(f"Unknown setting: {', '.join(sorted(unknown))}")

        download_dir = data.get("download_dir", "downloads")
        quality = data.get("quality", "best")
        keep_video = data.get("keep_video", False)
        if not isinstance(download_dir, str) or not download_dir.strip():
            raise ValueError("download_dir must be a nonempty string.")
        if not isinstance(quality, str) or quality not in {"best", "compatible"}:
            raise ValueError("quality must be 'best' or 'compatible'.")
        if not isinstance(keep_video, bool):
            raise ValueError("keep_video must be true or false.")
        return cls(download_dir=download_dir, quality=quality, keep_video=keep_video)


def config_path() -> Path:
    override = os.environ.get("YTDL_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "yt-downloader" / "config.json"


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Settings.from_dict(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid config at {path}: {exc}") from exc


def save_settings(settings: Settings) -> None:
    Settings.from_dict(asdict(settings))
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(asdict(settings), temporary, indent=2)
            temporary.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
