import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ytdl.cli import create_parser
from ytdl.downloader import YTDownloader


class FakeYoutubeDL:
    """Stands in for yt-dlp: a two-video playlist, and per-video downloads that
    write a file and honour the download archive like the real thing."""

    calls = []
    title = "My / Playlist"
    fail_ids = set()
    lock = threading.Lock()

    def __init__(self, options):
        self.options = options
        with self.lock:
            self.calls.append(options)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, url, download=False):
        if not download:
            return {
                "_type": "playlist",
                "title": self.title,
                "entries": [
                    {"id": "a", "ie_key": "Youtube", "url": "a", "title": "First"},
                    {"id": "b", "ie_key": "Youtube", "url": "b", "title": "Second"},
                ],
            }

        video_id = url.rsplit("=", 1)[-1].rsplit("/", 1)[-1]
        if video_id in self.fail_ids:
            raise RuntimeError(f"Video {video_id} is unavailable")

        archive = self.options.get("download_archive")
        if archive and Path(archive).exists() and video_id in Path(archive).read_text().split():
            return None

        name = self.options["outtmpl"].replace("%(title).150B", f"Video {video_id}").replace("%(id)s", video_id).replace("%(ext)s", "mp4")
        path = Path(name.replace("%%", "%"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"video {video_id}".encode())
        if archive:
            with self.lock, open(archive, "a") as handle:
                handle.write(f"youtube {video_id}\n")
        return {"id": video_id, "title": f"Video {video_id}", "height": 1080, "fps": 30,
                "requested_downloads": [{"filepath": str(path)}]}


def fake_ydl():
    FakeYoutubeDL.calls = []
    FakeYoutubeDL.title = "My / Playlist"
    FakeYoutubeDL.fail_ids = set()
    return patch("ytdl.downloader.YoutubeDL", FakeYoutubeDL)


def download_calls():
    return [call for call in FakeYoutubeDL.calls if "outtmpl" in call]


class PlaylistTest(unittest.TestCase):
    def test_playlist_download_uses_title_folder_and_numbered_names(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            downloader = YTDownloader(download_dir=directory)
            folder = downloader.download_playlist("https://www.youtube.com/playlist?list=example")

            self.assertEqual(folder, Path(directory) / "My _ Playlist")
            self.assertEqual(
                sorted(path.name for path in folder.glob("*.mp4")),
                ["001 - Video a [a].mp4", "002 - Video b [b].mp4"],
            )
            self.assertEqual(len(downloader.videos()), 2)
            self.assertEqual(download_calls()[0]["format"], "bv+ba/b")

            downloader.clear(videos=True, audio=False, force=True)
            self.assertFalse(folder.exists())

    def test_second_run_skips_downloaded_videos_unless_forced(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            downloader = YTDownloader(download_dir=directory)
            folder = downloader.download_playlist("https://example.com/list")
            (folder / "001 - Video a [a].mp4").unlink()

            downloader.download_playlist("https://example.com/list")
            self.assertFalse((folder / "001 - Video a [a].mp4").exists())

            downloader.download_playlist("https://example.com/list", skip_downloaded=False)
            self.assertTrue((folder / "001 - Video a [a].mp4").exists())
            self.assertNotIn("download_archive", download_calls()[-1])

    def test_clear_forgets_the_archive(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            downloader = YTDownloader(download_dir=directory)
            folder = downloader.download_playlist("https://example.com/list")
            downloader.clear(videos=True, audio=False, force=True)
            self.assertFalse((folder / YTDownloader.ARCHIVE_NAME).exists())

            downloader.download_playlist("https://example.com/list")
            self.assertEqual(len(list(folder.glob("*.mp4"))), 2)

    def test_percent_in_playlist_title_is_escaped_for_output_template(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            FakeYoutubeDL.title = "100% Hits"
            folder = YTDownloader(download_dir=directory).download_playlist("https://example.com/list")
            self.assertEqual(folder, Path(directory) / "100% Hits")
            self.assertEqual(len(list(folder.glob("*.mp4"))), 2)
            self.assertIn("100%% Hits", download_calls()[0]["outtmpl"])

    def test_playlist_first_limits_entries(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            folder = YTDownloader(download_dir=directory).download_playlist(
                "https://example.com/list", first=1
            )
            self.assertEqual(FakeYoutubeDL.calls[0]["playlistend"], 1)
            self.assertEqual([path.name for path in folder.glob("*.mp4")], ["001 - Video a [a].mp4"])

    def test_one_failed_video_does_not_stop_the_playlist(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            FakeYoutubeDL.fail_ids = {"a"}
            folder = YTDownloader(download_dir=directory).download_playlist("https://example.com/list")
            self.assertEqual([path.name for path in folder.glob("*.mp4")], ["002 - Video b [b].mp4"])

    def test_playlist_command_accepts_compatibility_mode(self):
        args = create_parser().parse_args(["playlist", "https://www.youtube.com/playlist?list=example", "--compatible"])
        self.assertEqual(args.command, "playlist")
        self.assertEqual(args.quality_override, "compatible")


class BatchTest(unittest.TestCase):
    URLS = [f"https://www.youtube.com/watch?v={video_id}" for video_id in "abcdef"]

    def test_parallel_batch_downloads_everything(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            paths = YTDownloader(download_dir=directory).download_many(self.URLS, jobs=4)
            self.assertEqual(len(paths), 6)
            self.assertEqual(len(list(Path(directory).glob("*.mp4"))), 6)

    def test_batch_reports_failures_and_skips(self):
        with tempfile.TemporaryDirectory() as directory, fake_ydl():
            downloader = YTDownloader(download_dir=directory)
            downloader.download_many(self.URLS[:2])
            FakeYoutubeDL.fail_ids = {"c"}
            paths = downloader.download_many(self.URLS[:3], jobs=2)
            self.assertEqual(paths, [])
            self.assertEqual(len(list(Path(directory).glob("*.mp4"))), 2)


class SlowYoutubeDL(FakeYoutubeDL):
    """A download that would take five seconds, reporting progress as it goes."""

    def extract_info(self, url, download=False):
        for done in range(500):
            for hook in self.options["progress_hooks"]:
                hook({"status": "downloading", "downloaded_bytes": done, "total_bytes": 500})
            time.sleep(0.01)
        return super().extract_info(url, download)


class CancelTest(unittest.TestCase):
    def test_ctrl_c_stops_running_downloads_promptly(self):
        def interrupted(futures):
            time.sleep(0.2)
            raise KeyboardInterrupt
            yield

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("ytdl.downloader.YoutubeDL", SlowYoutubeDL),
            patch("ytdl.downloader.as_completed", interrupted),
        ):
            start = time.monotonic()
            with self.assertRaises(KeyboardInterrupt):
                YTDownloader(download_dir=directory).download_many(BatchTest.URLS, jobs=3)
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(list(Path(directory).glob("*.mp4")), [])


if __name__ == "__main__":
    unittest.main()
