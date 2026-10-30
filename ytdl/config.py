"""Persistent defaults for the ytdl command."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


APP_NAME = "ytdl"
LEGACY_APP_NAME = "yt-downloader"
DEFAULT_DOWNLOAD_DIR = str(Path("~") / "Downloads" / APP_NAME)
SETTING_NAMES = {"download_dir", "quality", "keep_video", "check_updates"}


@dataclass(frozen=True)
class Settings:
    download_dir: str = DEFAULT_DOWNLOAD_DIR
    quality: Literal["best", "compatible"] = "best"
    keep_video: bool = False
    check_updates: bool = True

    @classmethod
    def from_dict(cls, data: object) -> Settings:
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object.")
        unknown = set(data) - SETTING_NAMES
        if unknown:
            raise ValueError(f"Unknown setting: {', '.join(sorted(unknown))}")

        download_dir = data.get("download_dir", DEFAULT_DOWNLOAD_DIR)
        quality = data.get("quality", "best")
        keep_video = data.get("keep_video", False)
        check_updates = data.get("check_updates", True)
        if not isinstance(download_dir, str) or not download_dir.strip():
            raise ValueError("download_dir must be a nonempty string.")
        if not isinstance(quality, str) or quality not in {"best", "compatible"}:
            raise ValueError("quality must be 'best' or 'compatible'.")
        if not isinstance(keep_video, bool):
            raise ValueError("keep_video must be true or false.")
        if not isinstance(check_updates, bool):
            raise ValueError("check_updates must be true or false.")
        return cls(
            download_dir=download_dir,
            quality=quality,
            keep_video=keep_video,
            check_updates=check_updates,
        )


def _config_override() -> Path | None:
    override = os.environ.get("YTDL_CONFIG_FILE") or os.environ.get("YT_DOWNLOADER_CONFIG_FILE")
    return Path(override).expanduser() if override else None


def _config_base() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _cache_base() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def config_path() -> Path:
    return _config_override() or _config_base() / APP_NAME / "config.json"


def state_path() -> Path:
    """Where ytdl keeps non-setting state, such as the last update check."""
    override = _config_override()
    if override:
        return override.with_name("update-check.json")
    return _cache_base() / APP_NAME / "update-check.json"


def legacy_config_paths() -> list[Path]:
    """Config locations used before the CLI was renamed to ytdl."""
    paths = []
    if os.name == "nt" and os.environ.get("APPDATA"):
        paths.append(Path(os.environ["APPDATA"]) / LEGACY_APP_NAME / "config.json")
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    paths.append(xdg / LEGACY_APP_NAME / "config.json")
    return paths


def _migrate_legacy_config(path: Path) -> None:
    if _config_override() or path.exists():
        return
    for legacy in legacy_config_paths():
        if legacy.is_file():
            try:
                settings = Settings.from_dict(json.loads(legacy.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                return
            # Move rather than copy, so `config reset` does not bring it back.
            save_settings(settings)
            legacy.unlink(missing_ok=True)
            try:
                legacy.parent.rmdir()
            except OSError:
                pass
            return


def load_settings() -> Settings:
    path = config_path()
    _migrate_legacy_config(path)
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Settings.from_dict(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid config at {path}: {exc}") from exc


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(data, temporary, indent=2)
            temporary.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_settings(settings: Settings) -> None:
    Settings.from_dict(asdict(settings))
    write_json(config_path(), asdict(settings))
