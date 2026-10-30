import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name)

    return name.strip()


def ensure_extension(
    filename: str,
    extension: str,
) -> str:
    path = Path(filename)

    if path.suffix.lower() != extension.lower():
        return filename + extension

    return filename


def format_size(size: int) -> str:
    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    value = float(size)

    for unit in units:
        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} PB"
