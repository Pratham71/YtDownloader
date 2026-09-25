"""Run with YT_DOWNLOAD_LIVE_TEST=1 to check the real YouTube download path."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from yt_downloader.downloader import YTDownloader


@unittest.skipUnless(os.environ.get("YT_DOWNLOAD_LIVE_TEST") == "1", "requires YouTube access")
class LiveDownloadTest(unittest.TestCase):
    def test_compatible_download_returns_h264_mp4_with_aac_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            path = YTDownloader(download_dir=directory).download(
                "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                filename="sample",
                compatible=True,
            )

            self.assertEqual(path, Path(directory) / "sample.mp4")
            self.assertGreater(path.stat().st_size, 0)
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "stream=codec_name,codec_type",
                    "-of", "csv=p=0",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(set(probe.stdout.splitlines()), {"h264,video", "aac,audio"})


if __name__ == "__main__":
    unittest.main()
