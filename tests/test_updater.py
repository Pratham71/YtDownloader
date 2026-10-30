import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ytdl import updater
from ytdl.cli import run_cli
from ytdl.config import Settings, load_settings


class VersionTest(unittest.TestCase):
    def test_versions_compare_numerically(self):
        self.assertTrue(updater.is_newer("0.10.0", "0.9.1"))
        self.assertTrue(updater.is_newer("2026.10.2", "2026.8.19"))
        self.assertFalse(updater.is_newer("0.2.0", "0.2.0"))
        self.assertFalse(updater.is_newer(None, "0.2.0"))


class UpdateCheckTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Path(self.directory.name) / "config.json"
        self.env = patch.dict(os.environ, {"YTDL_CONFIG_FILE": str(self.config)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_check_caches_latest_versions_and_reports_notices(self):
        with (
            patch("ytdl.updater.latest_ytdl_version", return_value="99.0.0"),
            patch("ytdl.updater.latest_yt_dlp_version", return_value="9999.1.1"),
        ):
            status = updater.check_for_updates()
        self.assertTrue(status.ytdl_outdated)
        self.assertTrue(status.yt_dlp_outdated)
        self.assertFalse(updater.check_is_due())

        notices = updater.BackgroundCheck().notices()
        self.assertEqual(len(notices), 2)
        self.assertIn("ytdl update", notices[0])

    def test_network_failure_is_not_an_error(self):
        with (
            patch("ytdl.updater.latest_ytdl_version", side_effect=OSError("offline")),
            patch("ytdl.updater.latest_yt_dlp_version", side_effect=OSError("offline")),
        ):
            status = updater.check_for_updates()
        self.assertIsNone(status.latest)
        self.assertFalse(status.ytdl_outdated)

    def test_stale_check_is_due_again(self):
        state = Path(self.directory.name) / "update-check.json"
        state.write_text(json.dumps({"checked_at": time.time() - 2 * 86400}), encoding="utf-8")
        self.assertTrue(updater.check_is_due())

    def test_update_dry_run_prints_commands_without_running_them(self):
        with (
            patch("ytdl.updater.latest_ytdl_version", return_value="0.0.1"),
            patch("ytdl.updater.latest_yt_dlp_version", return_value="0.0.1"),
            patch("ytdl.updater.install_method", return_value="uv"),
            patch("ytdl.updater.shutil.which", return_value="uv"),
            patch("ytdl.updater.run_update") as run,
            redirect_stdout(io.StringIO()),
        ):
            run_cli(["update", "--dry-run"])
        run.assert_not_called()

    def test_update_commands_for_each_install_method(self):
        with patch("ytdl.updater.shutil.which", side_effect=lambda tool: tool):
            self.assertEqual(
                updater.update_commands("uv"),
                [["uv", "tool", "install", "--force", "--upgrade", updater.INSTALL_SPEC]],
            )
            self.assertEqual(updater.update_commands("pipx")[0][:3], ["pipx", "install", "--force"])
            self.assertIn("--upgrade", updater.update_commands("pip")[0])
            self.assertEqual(updater.update_commands("source")[0][-2:], ["pull", "--ff-only"])

    def test_check_updates_setting_round_trips(self):
        run_cli(["config", "set", "check-updates", "false"])
        self.assertFalse(load_settings().check_updates)
        self.assertEqual(Settings().check_updates, True)


class LegacyConfigTest(unittest.TestCase):
    def test_old_yt_downloader_config_is_moved_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "yt-downloader" / "config.json"
            legacy.parent.mkdir()
            legacy.write_text(json.dumps({"quality": "compatible"}), encoding="utf-8")
            new = root / "ytdl" / "config.json"
            with (
                patch.dict(os.environ, {"YTDL_CONFIG_FILE": "", "YT_DOWNLOADER_CONFIG_FILE": ""}),
                patch("ytdl.config._config_base", return_value=root),
                patch("ytdl.config.legacy_config_paths", return_value=[legacy]),
            ):
                self.assertEqual(load_settings().quality, "compatible")
                self.assertTrue(new.exists())
                self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
