import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_downloader.cli import create_parser
from yt_downloader.downloader import YTDownloader


class FakeYoutubeDL:
    calls = []
    title = "My / Playlist"

    def __init__(self, options):
        self.options = options
        self.calls.append(options)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, url, download=False):
        if not download:
            return {"_type": "playlist", "title": self.title, "entries": [{"id": "a"}, {"id": "b"}]}
        folder = Path(self.options["outtmpl"].replace("%%", "%")).parent
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "001 - First.mp4").write_bytes(b"video one")
        (folder / "002 - Second.mp4").write_bytes(b"video two")
        return {"_type": "playlist", "entries": [{"id": "a"}, {"id": "b"}]}


class PlaylistTest(unittest.TestCase):
    def test_playlist_download_uses_title_folder_and_library_sees_videos(self):
        FakeYoutubeDL.calls = []
        FakeYoutubeDL.title = "My / Playlist"
        with tempfile.TemporaryDirectory() as directory, patch("yt_downloader.downloader.YoutubeDL", FakeYoutubeDL):
            downloader = YTDownloader(download_dir=directory)
            folder = downloader.download_playlist("https://www.youtube.com/playlist?list=example")

            self.assertEqual(folder, Path(directory) / "My _ Playlist")
            self.assertEqual(len(downloader.videos()), 2)
            self.assertEqual(downloader.total_size(), len(b"video one") + len(b"video two"))
            self.assertFalse(FakeYoutubeDL.calls[1]["noplaylist"])
            self.assertEqual(FakeYoutubeDL.calls[1]["format"], "bv+ba/b")

            downloader.clear(videos=True, audio=False, force=True)
            self.assertFalse(folder.exists())

    def test_percent_in_playlist_title_is_escaped_for_output_template(self):
        FakeYoutubeDL.calls = []
        FakeYoutubeDL.title = "100% Hits"
        with tempfile.TemporaryDirectory() as directory, patch("yt_downloader.downloader.YoutubeDL", FakeYoutubeDL):
            folder = YTDownloader(download_dir=directory).download_playlist("https://www.youtube.com/playlist?list=example")
            self.assertEqual(folder, Path(directory) / "100% Hits")
            self.assertEqual(len(list(folder.glob("*.mp4"))), 2)
            self.assertIn("100%% Hits", FakeYoutubeDL.calls[1]["outtmpl"])

    def test_playlist_command_accepts_compatibility_mode(self):
        args = create_parser().parse_args(["playlist", "https://www.youtube.com/playlist?list=example", "--compatible"])
        self.assertEqual(args.command, "playlist")
        self.assertEqual(args.quality_override, "compatible")

    def test_playlist_first_only_limits_download_pass(self):
        FakeYoutubeDL.calls = []
        FakeYoutubeDL.title = "My / Playlist"
        with tempfile.TemporaryDirectory() as directory, patch("yt_downloader.downloader.YoutubeDL", FakeYoutubeDL):
            YTDownloader(download_dir=directory).download_playlist("https://example.com/list", first=1)
            self.assertNotIn("playlistend", FakeYoutubeDL.calls[0])
            self.assertEqual(FakeYoutubeDL.calls[1]["playlistend"], 1)

    def test_height_cap_applies_to_both_quality_modes(self):
        best = YTDownloader._video_options(compatible=False, max_height=1080)
        compatible = YTDownloader._video_options(compatible=True, max_height=720)
        self.assertIn("bv[height<=1080]+ba", best["format"])
        self.assertIn("b[height<=1080]", best["format"])
        self.assertIn("bv[vcodec^=avc1][ext=mp4][height<=720]+ba", compatible["format"])


if __name__ == "__main__":
    unittest.main()
