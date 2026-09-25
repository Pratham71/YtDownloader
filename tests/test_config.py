import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from yt_downloader.cli import create_parser, run_cli
from yt_downloader.config import Settings, config_path, load_settings, save_settings
from yt_downloader.models import VideoInfo


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

    def test_info_survives_windows_legacy_output_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            info = VideoInfo("東京", "Channel", 19, 10, "https://example.com/video")
            with io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as output:
                with (
                    patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}),
                    patch("sys.stdout", output),
                    patch("yt_downloader.downloader.YTDownloader.info", return_value=info),
                ):
                    run_cli(["--dir", str(Path(directory) / "videos"), "info", info.url])
                output.flush()
                self.assertIn(b"Channel", output.buffer.getvalue())

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
                        "https://example.com/video", filename=None, compatible=True, max_height=None
                    )

                    run_cli(["--dir", str(Path(directory) / "other"), "playlist", "https://example.com/list", "--best"])
                    downloader.assert_called_with(download_dir=str(Path(directory) / "other"))
                    downloader.return_value.download_playlist.assert_called_with(
                        "https://example.com/list", compatible=False, max_height=None, first=None
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

    def test_video_limits_reach_downloader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with (
                patch.dict(os.environ, {"YT_DOWNLOADER_CONFIG_FILE": str(path)}),
                patch("yt_downloader.cli.YTDownloader") as downloader,
            ):
                run_cli(["download", "https://example.com/video", "--max-height", "1080"])
                downloader.return_value.download.assert_called_with(
                    "https://example.com/video", filename=None, compatible=False, max_height=1080
                )

                run_cli(["playlist", "https://example.com/list", "--first", "2", "--max-height", "720"])
                downloader.return_value.download_playlist.assert_called_with(
                    "https://example.com/list", compatible=False, max_height=720, first=2
                )

                run_cli(["grab", "cats", "--max-height", "480"])
                downloader.return_value.download_search_result.assert_called_with(
                    "cats", index=1, compatible=False, max_height=480
                )

                run_cli(["batch", "https://example.com/video", "--max-height", "360"])
                downloader.return_value.download_many.assert_called_with(
                    ["https://example.com/video"], compatible=False, max_height=360
                )

    def test_video_limits_require_positive_numbers(self):
        parser = create_parser()
        for arguments in (
            ["download", "https://example.com/video", "--max-height", "0"],
            ["playlist", "https://example.com/list", "--first", "-2"],
        ):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(arguments)


if __name__ == "__main__":
    unittest.main()
