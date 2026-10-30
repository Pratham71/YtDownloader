import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ytdl.cli import create_parser, error_message, read_url_file, run_cli
from ytdl.config import load_settings
from ytdl.downloader import YTDownloader, parse_browser


def keys(options):
    return [processor["key"] for processor in options.get("postprocessors", [])]


class FormatTest(unittest.TestCase):
    def test_height_cap_applies_to_both_quality_modes(self):
        best = YTDownloader.format_selector(compatible=False, max_height=1080)
        compatible = YTDownloader.format_selector(compatible=True, max_height=720)
        self.assertEqual(best, "bv[height<=?1080]+ba/b[height<=?1080]")
        self.assertIn("[height<=?720]+ba[ext=m4a]", compatible)

    def test_compatible_mode_accepts_h264_named_either_way(self):
        # YouTube says avc1; TikTok and Instagram say h264.
        self.assertIn("vcodec~='^(avc1|h264)'", YTDownloader.format_selector(compatible=True))

    def test_chosen_format_gets_best_audio_when_video_only(self):
        self.assertEqual(YTDownloader.format_selector(format_id="137"), "137+ba/137")


class PostprocessingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def make(self, **options):
        return YTDownloader(download_dir=self.directory.name, **options)

    def test_metadata_and_thumbnail_are_embedded_by_default(self):
        options = self.make()._video_options()
        self.assertEqual(keys(options), ["FFmpegMetadata", "EmbedThumbnail"])
        self.assertTrue(options["writethumbnail"])

    def test_metadata_can_be_turned_off(self):
        self.assertEqual(keys(self.make(embed_metadata=False)._video_options()), [])

    def test_subtitles_are_downloaded_and_embedded(self):
        options = self.make(subtitles="en,es")._video_options()
        self.assertIn("FFmpegEmbedSubtitle", keys(options))
        self.assertEqual(options["subtitleslangs"], ["en", "es"])
        self.assertTrue(options["writeautomaticsub"])

    def test_mp3_is_extracted_before_tagging(self):
        options = self.make(subtitles="en")._postprocessing_options(audio=True)
        self.assertEqual(keys(options), ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"])
        self.assertNotIn("writesubtitles", options)


class CookiesTest(unittest.TestCase):
    def test_browser_names_and_profiles(self):
        self.assertEqual(parse_browser("Chrome"), ("chrome", None, None, None))
        self.assertEqual(parse_browser("firefox:work"), ("firefox", "work", None, None))
        self.assertIsNone(parse_browser("none"))
        with self.assertRaisesRegex(ValueError, "Unsupported browser"):
            parse_browser("netscape")

    def test_cookies_reach_yt_dlp(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookies.txt"
            cookie_file.write_text("# Netscape HTTP Cookie File\n")
            options = YTDownloader(
                download_dir=directory, cookies_from_browser="edge", cookie_file=cookie_file
            )._ydl_options()
            self.assertEqual(options["cookiesfrombrowser"][0], "edge")
            self.assertEqual(options["cookiefile"], str(cookie_file))

    def test_missing_cookie_file_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileNotFoundError):
            YTDownloader(download_dir=directory, cookie_file=Path(directory) / "missing.txt")

    def test_login_errors_suggest_browser_cookies(self):
        message = error_message(RuntimeError("ERROR: [Instagram] abc: Requested content requires login"))
        self.assertIn("--cookies-from-browser", message)
        self.assertNotIn("--cookies-from-browser", error_message(RuntimeError("Video unavailable")))

    def test_site_names_in_errors_are_not_eaten_as_markup(self):
        self.assertIn("\\[vimeo]", error_message(RuntimeError("ERROR: [vimeo] 1: Not found")))


class EntryUrlTest(unittest.TestCase):
    def test_youtube_ids_become_watch_urls_and_other_sites_keep_theirs(self):
        self.assertEqual(
            YTDownloader._entry_url({"id": "abc", "ie_key": "Youtube", "url": "abc"}),
            "https://www.youtube.com/watch?v=abc",
        )
        tiktok = "https://www.tiktok.com/@someone/video/123"
        self.assertEqual(YTDownloader._entry_url({"id": "123", "ie_key": "TikTok", "url": tiktok}), tiktok)


class DownloadedPathsTest(unittest.TestCase):
    def test_every_video_in_a_multi_video_post_is_reported(self):
        carousel = {"_type": "playlist", "entries": [
            {"requested_downloads": [{"filepath": "one [a].mp4"}]},
            {"requested_downloads": [{"filepath": "two [b].mp4"}]},
        ]}
        self.assertEqual(YTDownloader._downloaded_paths(carousel, None), [Path("one [a].mp4"), Path("two [b].mp4")])

    def test_image_only_post_explains_what_happened(self):
        with self.assertRaisesRegex(RuntimeError, "only images"):
            YTDownloader._downloaded_paths({"_type": "playlist", "entries": []}, None)

    def test_names_include_the_id_and_custom_names_are_numbered_for_posts(self):
        self.assertIn("[%(id)s]", YTDownloader._output_name(None))
        # Check the templates the way yt-dlp evaluates them, not just as strings.
        from yt_dlp import YoutubeDL

        ydl = YoutubeDL({"quiet": True})
        custom = YTDownloader._output_name("clip.mp4")
        self.assertEqual(ydl.evaluate_outtmpl(custom, {"ext": "mp4"}), "clip.mp4")
        self.assertEqual(ydl.evaluate_outtmpl(custom, {"ext": "mp4", "playlist_index": 2}), "clip - 2.mp4")
        self.assertEqual(
            ydl.evaluate_outtmpl(YTDownloader._output_name(None), {"title": "A [b]", "id": "x1", "ext": "mkv"}),
            "A [b] [x1].mkv",
        )

    def test_audio_only_results_are_labelled(self):
        self.assertEqual(YTDownloader._quality_label({"vcodec": "none", "acodec": "opus"}), "audio only")
        self.assertEqual(YTDownloader._quality_label({"height": 1080, "fps": 60.0}), "1080p | 60 fps")


class FakeSearch:
    calls = 0

    def __init__(self, options):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, url, download=False):
        FakeSearch.calls += 1
        return {"entries": [
            {"id": f"v{n}", "title": f"Result {n}", "channel": "Chan", "duration": 61, "view_count": 1500}
            for n in range(int(url[len("ytsearch"):].split(":")[0]))
        ]}


class SearchCacheTest(unittest.TestCase):
    def test_repeated_search_is_served_from_cache(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"YTDL_CONFIG_FILE": str(Path(directory) / "config.json")}),
            patch("ytdl.downloader.YoutubeDL", FakeSearch),
        ):
            FakeSearch.calls = 0
            downloader = YTDownloader(download_dir=directory)
            first = downloader.search("lofi  Beats", limit=5)
            self.assertEqual(first[0]["url"], "https://www.youtube.com/watch?v=v0")
            self.assertEqual(first[0]["duration"], "1:01")

            self.assertEqual(downloader.search("LOFI beats", limit=3), first[:3])
            self.assertEqual(FakeSearch.calls, 1)

            downloader.search("lofi beats", limit=8)
            self.assertEqual(FakeSearch.calls, 2)


class CliOptionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"YTDL_CONFIG_FILE": str(Path(self.directory.name) / "config.json")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_new_settings_are_saved_and_validated(self):
        with redirect_stdout(io.StringIO()):
            run_cli(["config", "set", "cookies-from-browser", "firefox"])
            run_cli(["config", "set", "jobs", "3"])
            run_cli(["config", "set", "embed-metadata", "false"])
        settings = load_settings()
        self.assertEqual((settings.cookies_from_browser, settings.jobs, settings.embed_metadata), ("firefox", 3, False))

        for key, value in (("jobs", "99"), ("cookies-from-browser", "lynx")):
            with self.subTest(key=key), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                run_cli(["config", "set", key, value])

    def test_global_options_and_saved_jobs_reach_the_downloader(self):
        with redirect_stdout(io.StringIO()):
            run_cli(["config", "set", "jobs", "3"])
        with patch("ytdl.cli.YTDownloader") as downloader:
            run_cli([
                "--cookies-from-browser", "chrome", "--no-metadata",
                "batch", "https://example.com/a", "--subs", "--force",
            ])
        kwargs = downloader.call_args.kwargs
        self.assertEqual(kwargs["cookies_from_browser"], "chrome")
        self.assertFalse(kwargs["embed_metadata"])
        self.assertEqual(kwargs["subtitles"], "en.*")
        downloader.return_value.download_many.assert_called_with(
            ["https://example.com/a"], compatible=False, max_height=None, jobs=3, skip_downloaded=False
        )

    def test_batch_reads_urls_from_a_file(self):
        url_file = Path(self.directory.name) / "urls.txt"
        url_file.write_text("# my list\nhttps://example.com/a\n\n  https://example.com/b  \n")
        self.assertEqual(read_url_file(str(url_file)), ["https://example.com/a", "https://example.com/b"])

        with patch("ytdl.cli.YTDownloader") as downloader:
            run_cli(["batch", "https://example.com/c", "--file", str(url_file), "-j", "2"])
        self.assertEqual(
            downloader.return_value.download_many.call_args.args[0],
            ["https://example.com/c", "https://example.com/a", "https://example.com/b"],
        )

    def test_format_and_choose_reach_the_download(self):
        with patch("ytdl.cli.YTDownloader") as downloader:
            run_cli(["download", "https://example.com/v", "-f", "137"])
            self.assertEqual(downloader.return_value.download.call_args.kwargs["format_id"], "137")

            downloader.return_value.choose_format.return_value = "22"
            run_cli(["download", "https://example.com/v", "--choose"])
            self.assertEqual(downloader.return_value.download.call_args.kwargs["format_id"], "22")

    def test_jobs_are_limited(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            create_parser().parse_args(["batch", "https://example.com/a", "-j", "50"])


if __name__ == "__main__":
    unittest.main()
