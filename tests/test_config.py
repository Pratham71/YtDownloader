import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_downloader.cli import create_parser, run_cli
from yt_downloader.config import Settings, config_path, load_settings, save_settings


class SettingsTest(unittest.TestCase):
    def test_settings_round_trip_and_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}):
                self.assertEqual(load_settings(), Settings())
                self.assertFalse(path.exists())

                configured = Settings(
                    download_dir=str(Path(directory) / "videos"),
                    quality="compatible",
                    keep_video=True,
                )
                save_settings(configured)
                self.assertEqual(load_settings(), configured)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["quality"], "compatible")
                self.assertEqual(config_path(), path)

    def test_invalid_config_reports_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"quality": "ultra"}', encoding="utf-8")
            with patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}):
                with self.assertRaisesRegex(ValueError, "config.json"):
                    load_settings()

    def test_invalid_config_can_still_be_located_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{invalid json", encoding="utf-8")
            with patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}):
                run_cli(["config", "path"])
                run_cli(["config", "reset"])
                self.assertEqual(load_settings(), Settings())


class ConfigCliTest(unittest.TestCase):
    def test_help_uses_app_command_name(self):
        self.assertEqual(create_parser().prog, "yt-downloader")

    def test_saved_defaults_apply_and_one_run_overrides_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}):
                run_cli(["config", "set", "download-dir", str(Path(directory) / "videos")])
                run_cli(["config", "set", "quality", "compatible"])
                run_cli(["config", "set", "keep-video", "true"])

                with patch("yt_downloader.cli.YTDownloader") as downloader:
                    run_cli(["download", "https://example.com/video"])
                    downloader.assert_called_with(download_dir=str(Path(directory) / "videos"))
                    downloader.return_value.download.assert_called_with(
                        "https://example.com/video", filename=None, compatible=True
                    )

                    run_cli(["--dir", str(Path(directory) / "other"), "playlist", "https://example.com/list", "--best"])
                    downloader.assert_called_with(download_dir=str(Path(directory) / "other"))
                    downloader.return_value.download_playlist.assert_called_with(
                        "https://example.com/list", compatible=False
                    )

                    run_cli(["audio", "https://example.com/audio"])
                    downloader.return_value.download_mp3.assert_called_with(
                        "https://example.com/audio", delete_video=False
                    )

                    run_cli(["audio", "https://example.com/audio", "--delete-video"])
                    downloader.return_value.download_mp3.assert_called_with(
                        "https://example.com/audio", delete_video=True
                    )

                run_cli(["config", "reset"])
                self.assertFalse(path.exists())
                self.assertEqual(load_settings(), Settings())


if __name__ == "__main__":
    unittest.main()
