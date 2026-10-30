import re
from pathlib import Path

from rich.markup import escape


# C0 and C1 control characters, including ESC, except tab and newline.
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# Names Windows reserves for devices, with or without an extension.
WINDOWS_RESERVED_NAMES = re.compile(r"^(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(\..*)?$", re.I)


def display(text: object) -> str:
    """Make text from a website safe to print with rich.

    Titles, channel names, and error messages come from the site being
    downloaded. Terminal escape sequences in them could rewrite the screen,
    plant links, or set the clipboard, and square brackets would be read as
    rich markup, so remove the first and escape the second.
    """
    return escape(CONTROL_CHARACTERS.sub("", str(text)))


def sanitize_filename(name: str) -> str:
    name = CONTROL_CHARACTERS.sub("", name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip()

    if WINDOWS_RESERVED_NAMES.match(name):
        name = f"_{name}"

    return name


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
