"""Operating-system helpers: finding external tools and opening folders."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def os_name() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _linux_install(package: str) -> str:
    managers = [
        ("apt-get", f"sudo apt-get install {package}"),
        ("dnf", f"sudo dnf install {package}"),
        ("pacman", f"sudo pacman -S {package}"),
        ("zypper", f"sudo zypper install {package}"),
        ("apk", f"sudo apk add {package}"),
    ]
    for manager, command in managers:
        if shutil.which(manager):
            return command
    return f"Install {package} with your package manager"


def install_hint(tool: str) -> str:
    system = os_name()
    if tool == "ffmpeg":
        return {
            "windows": "winget install Gyan.FFmpeg",
            "macos": "brew install ffmpeg",
        }.get(system) or _linux_install("ffmpeg")
    if tool == "javascript":
        return {
            "windows": "winget install OpenJS.NodeJS.LTS",
            "macos": "brew install node",
        }.get(system) or "curl -fsSL https://deno.land/install.sh | sh"
    return f"Install {tool} and add it to PATH"


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(f"FFmpeg was not found on PATH. Install it with: {install_hint('ffmpeg')}")
    return path


def tool_version(executable: str) -> str | None:
    path = shutil.which(executable)
    if not path:
        return None
    flag = "-version" if executable in {"ffmpeg", "ffprobe"} else "--version"
    try:
        output = subprocess.run(
            [path, flag], capture_output=True, text=True, timeout=10, errors="replace"
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "found"
    first_line = output.strip().splitlines()[0] if output.strip() else "found"
    return first_line.removeprefix("ffmpeg version ").removeprefix("ffprobe version ").split(" Copyright")[0]


def platform_label() -> str:
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def open_folder(path: Path) -> bool:
    """Open a folder in the system file manager. Returns False when none is available."""
    system = os_name()
    if system == "windows":
        os.startfile(path)
        return True
    opener = "open" if system == "macos" else "xdg-open"
    if not shutil.which(opener):
        return False
    subprocess.Popen(
        [opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return True
