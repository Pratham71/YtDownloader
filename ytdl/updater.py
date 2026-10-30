"""Check for and install new versions of ytdl and yt-dlp."""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import state_path, write_json


REPO = "Pratham71/YtDownloader"
REPO_URL = f"https://github.com/{REPO}"
INSTALL_SPEC = f"git+{REPO_URL}.git"
REMOTE_PYPROJECT = f"https://raw.githubusercontent.com/{REPO}/main/pyproject.toml"
YT_DLP_PYPI = "https://pypi.org/pypi/yt-dlp/json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
SOURCE_ROOT = Path(__file__).resolve().parent.parent


def installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "0.0.0"


def current_version() -> str:
    return installed_version("ytdl")


def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text.split("+")[0]))


def is_newer(latest: str | None, current: str) -> bool:
    return latest is not None and parse_version(latest) > parse_version(current)


def _fetch(url: str, timeout: float) -> bytes:
    context = None
    try:
        # python.org builds on macOS ship without system certificates.
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    request = urllib.request.Request(
        url, headers={"User-Agent": f"ytdl/{current_version()}"}
    )
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.read()


def latest_ytdl_version(timeout: float = 5) -> str:
    return tomllib.loads(_fetch(REMOTE_PYPROJECT, timeout).decode("utf-8"))["project"]["version"]


def latest_yt_dlp_version(timeout: float = 5) -> str:
    return json.loads(_fetch(YT_DLP_PYPI, timeout))["info"]["version"]


@dataclass(frozen=True)
class UpdateStatus:
    current: str
    latest: str | None
    yt_dlp_current: str
    yt_dlp_latest: str | None

    @property
    def ytdl_outdated(self) -> bool:
        return is_newer(self.latest, self.current)

    @property
    def yt_dlp_outdated(self) -> bool:
        return is_newer(self.yt_dlp_latest, self.yt_dlp_current)


def _read_state() -> dict:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _status_from(state: dict) -> UpdateStatus:
    return UpdateStatus(
        current=current_version(),
        latest=state.get("latest"),
        yt_dlp_current=installed_version("yt-dlp"),
        yt_dlp_latest=state.get("yt_dlp_latest"),
    )


def check_for_updates(timeout: float = 5) -> UpdateStatus:
    """Ask GitHub and PyPI for the newest versions and cache the answer."""
    state = {"checked_at": time.time(), "latest": None, "yt_dlp_latest": None}
    try:
        state["latest"] = latest_ytdl_version(timeout)
    except Exception:
        pass
    try:
        state["yt_dlp_latest"] = latest_yt_dlp_version(timeout)
    except Exception:
        pass
    try:
        write_json(state_path(), state)
    except OSError:
        pass
    return _status_from(state)


def check_is_due() -> bool:
    checked_at = _read_state().get("checked_at")
    return not isinstance(checked_at, (int, float)) or time.time() - checked_at > CHECK_INTERVAL_SECONDS


class BackgroundCheck:
    """Refresh the cached update status at most once a day without blocking."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        if check_is_due():
            self._thread = threading.Thread(
                target=check_for_updates, kwargs={"timeout": 3}, daemon=True
            )
            self._thread.start()

    def notices(self, wait: float = 1.0) -> list[str]:
        if self._thread is not None:
            self._thread.join(wait)
        status = _status_from(_read_state())
        messages = []
        if status.ytdl_outdated:
            messages.append(
                f"ytdl {status.latest} is available (you have {status.current}). "
                "Run `ytdl update` to install it."
            )
        if status.yt_dlp_outdated:
            messages.append(
                f"yt-dlp {status.yt_dlp_latest} is available (you have {status.yt_dlp_current}). "
                "Run `ytdl update` if downloads stop working."
            )
        return messages


def update_checks_disabled() -> bool:
    return os.environ.get("YTDL_NO_UPDATE_CHECK", "").lower() in {"1", "true", "yes"}


# ============================================================
# INSTALLING UPDATES
# ============================================================


def install_method() -> str:
    """How this copy of ytdl was installed: source, uv, pipx, or pip."""
    if (SOURCE_ROOT / ".git").exists() and (SOURCE_ROOT / "pyproject.toml").exists():
        return "source"
    prefix = Path(sys.prefix)
    if (prefix / "uv-receipt.toml").exists():
        return "uv"
    if (prefix / "pipx_metadata.json").exists():
        return "pipx"
    return "pip"


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"`{tool}` was not found on PATH, so ytdl cannot update itself.")
    return path


def update_commands(method: str) -> list[list[str]]:
    match method:
        case "source":
            return [
                [_require("git"), "-C", str(SOURCE_ROOT), "pull", "--ff-only"],
                [_require("uv"), "sync", "--project", str(SOURCE_ROOT), "--upgrade-package", "yt-dlp"],
            ]
        case "uv":
            return [[_require("uv"), "tool", "install", "--force", "--upgrade", INSTALL_SPEC]]
        case "pipx":
            return [[_require("pipx"), "install", "--force", INSTALL_SPEC]]
        case _:
            return [[
                sys.executable, "-m", "pip", "install", "--upgrade",
                "--upgrade-strategy", "eager", INSTALL_SPEC,
            ]]


def _run_detached_on_windows(commands: list[list[str]]) -> None:
    """Windows cannot replace the running ytdl.exe or python.exe, so the update
    runs in a new console window once this process has exited."""
    lines = [
        "@echo off",
        "echo Waiting for ytdl to exit...",
        "timeout /t 2 /nobreak >nul",
    ]
    for command in commands:
        lines += [subprocess.list2cmdline(command), "if errorlevel 1 goto failed"]
    lines += [
        "echo.",
        "echo ytdl is up to date. Run `ytdl --version` to confirm.",
        "pause",
        "goto end",
        ":failed",
        "echo.",
        "echo The update failed. See the messages above.",
        "pause",
        ":end",
        '(goto) 2>nul & del "%~f0"',
    ]
    script = Path(tempfile.mkdtemp(prefix="ytdl-update-")) / "update.cmd"
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        close_fds=True,
    )


def run_update(commands: list[list[str]], method: str) -> bool:
    """Run the update. Returns False when it continues in another window."""
    if os.name == "nt" and method != "source":
        _run_detached_on_windows(commands)
        return False
    for command in commands:
        subprocess.run(command, check=True)
    # Forget the cached check so the "update available" notice goes away.
    state_path().unlink(missing_ok=True)
    return True
