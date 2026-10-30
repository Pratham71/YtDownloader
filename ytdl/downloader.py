from __future__ import annotations

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path
from time import perf_counter

import yt_dlp
from yt_dlp import YoutubeDL
from yt_dlp.cookies import SUPPORTED_BROWSERS

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from . import cache
from .models import VideoInfo
from .system import open_folder, require_ffmpeg
from .utils import (
    ensure_extension,
    format_size,
    sanitize_filename,
)


console = Console()


class DownloadCancelled(Exception):
    pass


def clean_error(exc: BaseException) -> str:
    """yt-dlp's message without its 'ERROR: ' prefix, safe to print with rich."""
    return escape(str(exc).removeprefix("ERROR: ").strip())


class _Logger:
    """Send yt-dlp's warnings to the ytdl console and leave errors to ytdl,
    which reports them once, with hints."""

    def debug(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        console.print(f"[yellow]Warning:[/yellow] [dim]{escape(message)}[/dim]")

    def error(self, message: str) -> None:
        pass


class YTDownloader:
    VIDEO_EXTENSIONS = {
        ".mp4",
        ".webm",
        ".mkv",
    }

    AUDIO_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".opus",
        ".ogg",
        ".flac",
    }

    # The video ID keeps names unique: many sites reuse titles such as
    # "Video by instagram", and later downloads would overwrite earlier ones.
    NAME_TEMPLATE = "%(title).150B [%(id)s].%(ext)s"

    # Batch and playlist downloads record finished video IDs here, per folder,
    # so running the same command again skips what is already downloaded.
    ARCHIVE_NAME = ".ytdl-archive.txt"

    def __init__(
        self,
        url: str | None = None,
        download_dir: str | Path = "downloads",
        cookies_from_browser: str | None = None,
        cookie_file: str | Path | None = None,
        embed_metadata: bool = True,
        subtitles: str | None = None,
    ):
        self.url = url

        self.download_dir = Path(download_dir).expanduser()
        self.audio_dir = self.download_dir / "mp3"
        self.cookies_from_browser = parse_browser(cookies_from_browser)
        self.cookie_file = Path(cookie_file).expanduser() if cookie_file else None
        self.embed_metadata = embed_metadata
        self.subtitles = subtitles
        self._cancel = threading.Event()

        if self.cookie_file and not self.cookie_file.is_file():
            raise FileNotFoundError(f"Cookie file not found: {self.cookie_file}")

        self.download_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.audio_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    def _require_url(
        self,
        url: str | None = None,
    ) -> str:
        final_url = url or self.url

        if not final_url:
            raise ValueError("No video URL was provided.")

        return final_url

    @staticmethod
    def _video_info(data: dict, url: str) -> VideoInfo:
        return VideoInfo(
            title=data.get("title") or data.get("id") or "Unknown",
            author=data.get("uploader") or data.get("channel") or "Unknown",
            duration_seconds=int(data.get("duration") or 0),
            views=data.get("view_count") or 0,
            url=data.get("webpage_url") or url,
            site=data.get("extractor_key") or data.get("ie_key") or "",
        )

    @staticmethod
    def _entry_url(entry: dict) -> str:
        for key in ("webpage_url", "url"):
            if str(entry.get(key) or "").startswith("http"):
                return entry[key]
        # YouTube's flat playlist and search entries carry only the video ID.
        if entry.get("id") and entry.get("ie_key", "Youtube") == "Youtube":
            return f"https://www.youtube.com/watch?v={entry['id']}"
        return entry.get("url") or ""

    def _ydl_options(self) -> dict:
        options = {
            "noplaylist": True,
            "quiet": True,
            "logger": _Logger(),
            # Deno works by default; explicitly enable Node when it is installed.
            "js_runtimes": {"deno": {}, "node": {}},
        }
        if self.cookies_from_browser:
            options["cookiesfrombrowser"] = self.cookies_from_browser
        if self.cookie_file:
            options["cookiefile"] = str(self.cookie_file)
        return options

    @staticmethod
    def format_selector(
        compatible: bool = False,
        max_height: int | None = None,
        format_id: str | None = None,
    ) -> str:
        if format_id:
            # A video-only format gets the best audio; anything else is used as is.
            return f"{format_id}+ba/{format_id}"
        # `<=?` also accepts formats that do not report a height, such as audio-only
        # formats and some Instagram videos.
        height_filter = f"[height<=?{max_height}]" if max_height is not None else ""
        if compatible:
            # YouTube names H.264 "avc1"; TikTok, Instagram, and others say "h264".
            h264 = "[vcodec~='^(avc1|h264)'][ext=mp4]"
            return (
                f"bv{h264}{height_filter}+ba[ext=m4a]/"
                f"b{h264}{height_filter}"
            )
        return f"bv{height_filter}+ba/b{height_filter}"

    def _postprocessing_options(self, audio: bool = False) -> dict:
        """Metadata, thumbnail, subtitle, and MP3 steps, built the way the yt-dlp CLI builds them."""
        argv = []
        if audio:
            argv += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        if self.embed_metadata:
            argv += ["--embed-metadata", "--embed-thumbnail"]
        if self.subtitles and not audio:
            argv += [
                "--write-subs", "--write-auto-subs",
                "--sub-langs", self.subtitles, "--embed-subs",
            ]
        if not argv:
            return {}

        parsed = yt_dlp.parse_options(argv).ydl_opts
        options = {
            key: parsed[key]
            for key in ("writethumbnail", "writesubtitles", "writeautomaticsub", "subtitleslangs")
            if parsed.get(key)
        }
        options["postprocessors"] = [
            processor for processor in parsed["postprocessors"]
            if processor["key"] != "FFmpegConcat"
        ]
        return options

    def _video_options(
        self,
        compatible: bool = False,
        max_height: int | None = None,
        format_id: str | None = None,
    ) -> dict:
        options = self._ydl_options()
        options.update(self._postprocessing_options())
        options.update(
            {
                "format": self.format_selector(compatible, max_height, format_id),
                "merge_output_format": "mp4" if compatible and not format_id else "mp4/mkv",
            }
        )
        if not compatible and not format_id:
            options["format_sort"] = ["res", "fps"]
            options["format_sort_force"] = True
        return options

    @staticmethod
    def _progress() -> Progress:
        return Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        )

    def _download_with_progress(
        self,
        url: str,
        options: dict,
        progress: Progress | None = None,
        label: str = "Downloading",
    ) -> tuple[dict | None, list[Path], float]:
        """Run yt-dlp with a progress bar; return its info, the files, and seconds taken.

        A post with several videos (an Instagram carousel, say) gives several files.
        The info is None and the list empty when the video is already in the
        download archive. Pass a shared ``progress`` to show several downloads at once.
        """
        progress_task = None
        options = {**options, "noprogress": True, "progress_hooks": []}
        shared = progress is not None
        progress = progress or self._progress()

        def on_progress(status: dict) -> None:
            nonlocal progress_task

            if self._cancel.is_set():
                raise DownloadCancelled("Cancelled.")

            if status["status"] not in {"downloading", "finished"}:
                return

            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            downloaded = status.get("downloaded_bytes") or total

            if progress_task is None:
                progress_task = progress.add_task(
                    label,
                    total=total or None,
                )

            progress.update(
                progress_task,
                total=total or None,
                completed=downloaded,
            )

        options["progress_hooks"].append(on_progress)
        try:
            with nullcontext() if shared else progress:
                start = perf_counter()
                with YoutubeDL(options) as ydl:
                    data = ydl.extract_info(url, download=True)
                    if data is None:
                        return None, [], perf_counter() - start
                    paths = self._downloaded_paths(data, ydl)
                elapsed = perf_counter() - start
        finally:
            if shared and progress_task is not None:
                progress.remove_task(progress_task)

        return data, paths, elapsed

    @staticmethod
    def _downloaded_paths(data: dict, ydl: YoutubeDL) -> list[Path]:
        entries = data.get("entries")
        items = [entry for entry in entries or [] if entry] if entries is not None else [data]
        paths = [
            Path(download["filepath"])
            for item in items
            for download in item.get("requested_downloads") or []
            if download.get("filepath")
        ]
        if not paths and entries is None:
            paths = [Path(ydl.prepare_filename(data))]
        if not paths:
            raise RuntimeError(
                "Nothing to download here. The post may contain only images, "
                "which ytdl does not download."
            )
        return list(dict.fromkeys(paths))

    @staticmethod
    def _output_name(filename: str | None) -> str:
        if not filename:
            return YTDownloader.NAME_TEMPLATE
        filename = sanitize_filename(filename)
        suffix = Path(filename).suffix.lower()
        if suffix in YTDownloader.VIDEO_EXTENSIONS:
            filename = filename[: -len(suffix)]
        # Number the files when the URL holds several videos: "name - 1.mp4", ...
        # (yt-dlp template fields cannot contain parentheses).
        return filename.replace("%", "%%") + "%(playlist_index& - {}|)s.%(ext)s"

    @staticmethod
    def _quality_label(data: dict) -> str:
        data = next((entry for entry in data.get("entries") or [] if entry), data)
        if data.get("vcodec") == "none":
            return "audio only"
        # Merged downloads may only report the height on the formats they combined.
        height = data.get("height") or max(
            (item.get("height") or 0 for item in data.get("requested_formats") or []), default=0
        )
        fps = data.get("fps")
        quality = f"{height}p" if height else "Unknown resolution"
        if fps:
            quality += f" | {fps:g} fps"
        return quality

    # ========================================================
    # VIDEO INFO
    # ========================================================

    def info(
        self,
        url: str | None = None,
    ) -> VideoInfo:
        final_url = self._require_url(url)
        with YoutubeDL(self._ydl_options()) as ydl:
            data = ydl.extract_info(final_url, download=False)
        return self._video_info(data, final_url)

    @staticmethod
    def supported_sites(match: str | None = None) -> list[str]:
        """Names of the sites yt-dlp can download from, optionally filtered."""
        from yt_dlp.extractor import gen_extractor_classes

        unique: dict[str, str] = {}
        for extractor in gen_extractor_classes():
            name = extractor.IE_NAME.split(":")[0]
            if extractor.working() and name != "generic":
                # Prefer the capitalised spelling, e.g. "TikTok" over "tiktok".
                if name.lower() not in unique or name[:1].isupper():
                    unique[name.lower()] = name
        names = sorted(unique.values(), key=str.lower)
        if match:
            names = [name for name in names if match.lower() in name.lower()]
        return names

    def show_info(
        self,
        url: str | None = None,
    ) -> None:
        info = self.info(url)

        table = Table(
            title=f"{info.site or 'Video'} video",
            show_header=False,
            border_style="cyan",
        )

        table.add_column(
            "Property",
            style="bold cyan",
        )

        table.add_column("Value")

        table.add_row(
            "Title",
            escape(info.title),
        )

        table.add_row(
            "Channel",
            escape(info.author),
        )

        table.add_row(
            "Duration",
            info.duration,
        )

        table.add_row(
            "Views",
            info.readable_views,
        )

        table.add_row(
            "URL",
            escape(info.url),
        )

        console.print(table)

    # ========================================================
    # FORMATS
    # ========================================================

    def formats(
        self,
        url: str | None = None,
    ) -> list[dict]:
        """Available formats for a video, best first."""
        final_url = self._require_url(url)
        with YoutubeDL(self._ydl_options()) as ydl:
            data = ydl.extract_info(final_url, download=False)

        rows = []
        for item in reversed(data.get("formats") or []):
            if item.get("ext") == "mhtml" or "storyboard" in (item.get("format_note") or ""):
                continue
            has_video = (item.get("vcodec") or "none") != "none"
            has_audio = (item.get("acodec") or "none") != "none"
            if not has_video and not has_audio:
                continue
            size = item.get("filesize") or item.get("filesize_approx")
            rows.append(
                {
                    "id": str(item["format_id"]),
                    "ext": item.get("ext") or "?",
                    "resolution": f"{item['height']}p" if item.get("height") else "audio only",
                    "fps": f"{item['fps']:g}" if item.get("fps") else "",
                    "contents": "video+audio" if has_video and has_audio else ("video" if has_video else "audio"),
                    "codecs": " / ".join(
                        codec.split(".")[0]
                        for codec in (item.get("vcodec"), item.get("acodec"))
                        if codec and codec != "none"
                    ),
                    "size": format_size(size) if size else "",
                }
            )
        return rows

    def show_formats(
        self,
        url: str | None = None,
    ) -> list[dict]:
        rows = self.formats(url)

        table = Table(
            title="Available formats",
            border_style="cyan",
        )
        for column in ("ID", "Ext", "Resolution", "FPS", "Contents", "Codecs", "Size"):
            table.add_column(column, style="bold cyan" if column == "ID" else None, no_wrap=True)
        for row in rows:
            table.add_row(*(escape(value) for value in row.values()))

        console.print(table)
        console.print("[dim]Video-only formats are merged with the best audio automatically.[/dim]")
        return rows

    def choose_format(
        self,
        url: str | None = None,
    ) -> str | None:
        """Show the formats and ask for one. Returns None to keep the default quality."""
        rows = self.show_formats(url)
        ids = {row["id"] for row in rows}
        while True:
            answer = console.input("[cyan]Format ID (Enter for the default quality): [/cyan]").strip()
            if not answer:
                return None
            if answer in ids:
                return answer
            console.print(f"[red]'{answer}' is not in the list.[/red]")

    # ========================================================
    # VIDEO DOWNLOAD
    # ========================================================

    def download(
        self,
        url: str | None = None,
        filename: str | None = None,
        compatible: bool = False,
        max_height: int | None = None,
        format_id: str | None = None,
    ) -> Path:
        final_url = self._require_url(url)

        options = self._video_options(compatible, max_height, format_id)
        options["outtmpl"] = str(self.download_dir / self._output_name(filename))
        data, paths, elapsed = self._download_with_progress(final_url, options)

        info = self._video_info(data, final_url)

        console.print(
            Panel.fit(
                (
                    f"[bold]{escape(info.title)}[/bold]\n"
                    f"[dim]{escape(info.author)} | {info.duration} | "
                    f"{info.readable_views} views[/dim]\n"
                    f"[cyan]{self._quality_label(data)}[/cyan]"
                ),
                title=f"{info.site or 'Video'} video",
                border_style="cyan",
            )
        )

        console.print(
            Panel.fit(
                (
                    "[green bold]"
                    "Download complete"
                    "[/green bold]\n"
                    + "\n".join(escape(path.name) for path in paths)
                    + f"\n[dim]{elapsed:.2f}s[/dim]"
                ),
                border_style="green",
            )
        )

        return paths[0]

    def _download_entries(
        self,
        entries: list[tuple[str, str]],
        archive: Path | None,
        jobs: int = 1,
        compatible: bool = False,
        max_height: int | None = None,
    ) -> tuple[list[Path], int, int]:
        """Download (url, output template) pairs, up to ``jobs`` at a time.

        Returns the downloaded files, the number skipped because they were
        already downloaded, and the number that failed.
        """
        base = self._video_options(compatible, max_height)
        if archive is not None:
            base["download_archive"] = str(archive)

        downloaded: list[Path] = []
        skipped = failed = 0
        self._cancel.clear()

        progress = self._progress()

        def fetch(position: int, url: str, template: str) -> tuple[dict | None, list[Path]]:
            data, paths, _ = self._download_with_progress(
                url, {**base, "outtmpl": template}, progress=progress, label=f"#{position}"
            )
            return data, paths

        with progress, ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(fetch, position, url, template): url
                for position, (url, template) in enumerate(entries, start=1)
            }
            try:
                for finished, future in enumerate(as_completed(futures), start=1):
                    url = futures[future]
                    count = f"[dim]({finished}/{len(entries)})[/dim]"
                    try:
                        data, paths = future.result()
                    except Exception as exc:
                        failed += 1
                        progress.console.print(
                            f"{count} [red]Failed:[/red] {escape(url)}\n[dim]{clean_error(exc)}[/dim]"
                        )
                        continue
                    if data is None:
                        skipped += 1
                        progress.console.print(f"{count} [dim]Already downloaded: {escape(url)}[/dim]")
                        continue
                    downloaded.extend(paths)
                    for path in paths:
                        progress.console.print(
                            f"{count} [green]Done:[/green] {escape(path.name)} "
                            f"[dim]({self._quality_label(data)})[/dim]"
                        )
            except KeyboardInterrupt:
                # Stop the running downloads at their next progress update.
                self._cancel.set()
                pool.shutdown(wait=True, cancel_futures=True)
                raise

        return downloaded, skipped, failed

    def download_playlist(
        self,
        url: str | None = None,
        compatible: bool = False,
        max_height: int | None = None,
        first: int | None = None,
        jobs: int = 1,
        skip_downloaded: bool = True,
    ) -> Path:
        final_url = self._require_url(url)
        metadata_options = self._ydl_options()
        metadata_options.update({"noplaylist": False, "extract_flat": "in_playlist"})
        if first is not None:
            metadata_options["playlistend"] = first
        with YoutubeDL(metadata_options) as ydl:
            metadata = ydl.extract_info(final_url, download=False)

        if not metadata or metadata.get("_type") != "playlist":
            raise ValueError("The URL does not contain a playlist.")

        title = sanitize_filename(metadata.get("title") or metadata.get("id") or "Playlist")
        title = title.strip(" .") or "Playlist"
        folder = self.download_dir / title
        folder.mkdir(parents=True, exist_ok=True)
        folder_template = str(folder).replace("%", "%%") + os.sep

        entries = []
        for position, entry in enumerate(metadata.get("entries") or [], start=1):
            if first is not None and position > first:
                break
            if not entry:
                continue
            index = entry.get("playlist_index") or position
            entries.append(
                (self._entry_url(entry), folder_template + f"{index:03d} - {self.NAME_TEMPLATE}")
            )

        console.print(
            f"[cyan]Downloading playlist:[/cyan] [bold]{escape(title)}[/bold] "
            f"[dim]({len(entries)} videos)[/dim]"
        )
        downloaded, skipped, failed = self._download_entries(
            entries,
            archive=folder / self.ARCHIVE_NAME if skip_downloaded else None,
            jobs=jobs,
            compatible=compatible,
            max_height=max_height,
        )

        if not downloaded and not skipped:
            raise RuntimeError("No videos were downloaded from this playlist.")

        summary = f"{len(downloaded)} downloaded"
        if skipped:
            summary += f", {skipped} already there"
        if failed:
            summary += f", {failed} failed"
        console.print(f"[green]Playlist saved:[/green] {escape(str(folder))} ({summary})")
        return folder

    # ========================================================
    # AUDIO CONVERSION
    # ========================================================

    def to_mp3(
        self,
        video_path: str | Path,
        output_name: str | None = None,
        delete_video: bool = False,
    ) -> Path:
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        output_name = output_name or video_path.stem

        output_name = sanitize_filename(output_name)

        output_name = ensure_extension(
            output_name,
            ".mp3",
        )

        output_path = self.audio_dir / output_name

        console.print((f"\n[cyan]Converting:[/cyan] [bold]{escape(video_path.name)}[/bold]"))

        start = perf_counter()

        result = subprocess.run(
            [
                require_ffmpeg(),
                "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(video_path),
                "-map", "0:a", "-map_metadata", "0",
                "-codec:a", "libmp3lame", "-q:a", "0",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode != 0:
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg could not convert the video: {result.stderr.strip()}")

        elapsed = perf_counter() - start

        if delete_video:
            video_path.unlink()

        self._show_mp3_complete(output_path, elapsed)

        return output_path

    @staticmethod
    def _show_mp3_complete(path: Path, elapsed: float) -> None:
        console.print(
            Panel.fit(
                (
                    "[green bold]"
                    "MP3 conversion complete"
                    "[/green bold]\n"
                    f"{escape(path.name)}\n"
                    f"[dim]{elapsed:.2f}s[/dim]"
                ),
                border_style="green",
            )
        )

    def download_mp3(
        self,
        url: str | None = None,
        delete_video: bool = True,
    ) -> Path:
        if not delete_video:
            video = self.download(url, compatible=True)
            return self.to_mp3(video)

        # Without a video to keep, fetch only the audio stream: much smaller and faster.
        final_url = self._require_url(url)
        require_ffmpeg()
        options = self._ydl_options()
        options.update(self._postprocessing_options(audio=True))
        options.update(
            {
                "format": "ba/b",
                "outtmpl": str(self.audio_dir / self.NAME_TEMPLATE),
            }
        )
        _, paths, elapsed = self._download_with_progress(final_url, options)
        paths = [path.with_suffix(".mp3") for path in paths]
        for path in paths:
            self._show_mp3_complete(path, elapsed)
        return paths[0]

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")

        # Reuse recent results so `grab` picks the same video `search` showed.
        cached = cache.cached_search(query, limit)
        if cached is not None:
            return cached

        options = self._ydl_options()
        options["extract_flat"] = True
        with YoutubeDL(options) as ydl:
            data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

        results = []
        for entry in data.get("entries") or []:
            if not entry:
                continue
            url = self._entry_url(entry)
            info = self._video_info(entry, url)
            results.append(
                {
                    "title": info.title,
                    "channel": entry.get("channel") or info.author,
                    "duration": info.duration if info.duration_seconds else "Unknown",
                    "views": info.readable_views if entry.get("view_count") else "Unknown",
                    "url": url,
                }
            )
        cache.store_search(query, limit, results)
        return results

    def show_search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        results = self.search(
            query,
            limit,
        )

        table = Table(
            title=f'Search: "{escape(query)}"',
            border_style="magenta",
        )

        table.add_column(
            "#",
            style="cyan",
        )

        table.add_column("Title")
        table.add_column("Channel")
        table.add_column("Duration")
        table.add_column("Views")

        for index, video in enumerate(
            results,
            start=1,
        ):
            table.add_row(
                str(index),
                escape(video["title"]),
                escape(video["channel"]),
                video["duration"],
                video["views"],
            )

        console.print(table)

        return results

    def download_search_result(
        self,
        query: str,
        index: int = 1,
        compatible: bool = False,
        max_height: int | None = None,
    ) -> Path:
        results = self.search(
            query,
            limit=max(index, 5),
        )

        if index < 1 or index > len(results):
            raise IndexError("Invalid search result index.")

        selected = results[index - 1]

        console.print((f"[cyan]Selected:[/cyan] [bold]{escape(selected['title'])}[/bold]"))

        return self.download(
            selected["url"], compatible=compatible, max_height=max_height
        )

    # ========================================================
    # DOWNLOADED FILES
    # ========================================================

    def videos(
        self,
    ) -> list[Path]:
        return sorted(
            path
            for path in self.download_dir.rglob("*")
            if (path.is_file() and path.suffix.lower() in self.VIDEO_EXTENSIONS)
        )

    def audios(
        self,
    ) -> list[Path]:
        return sorted(
            path
            # Anywhere in the folder: audio-only sites save straight into it.
            for path in self.download_dir.rglob("*")
            if (path.is_file() and path.suffix.lower() in self.AUDIO_EXTENSIONS)
        )

    def downloads(
        self,
    ) -> list[Path]:
        return self.videos() + self.audios()

    def show_downloads(
        self,
    ) -> None:
        files = [("Video", path) for path in self.videos()]

        files.extend([("Audio", path) for path in self.audios()])

        if not files:
            console.print(("[yellow]No downloads found.[/yellow]"))
            return

        table = Table(
            title="Downloads",
            border_style="blue",
        )

        table.add_column("#")
        table.add_column("Type")
        table.add_column("Filename")
        table.add_column("Size")

        for index, (
            media_type,
            path,
        ) in enumerate(
            files,
            start=1,
        ):
            table.add_row(
                str(index),
                media_type,
                escape(str(path.relative_to(self.download_dir))),
                format_size(path.stat().st_size),
            )

        console.print(table)

    # ========================================================
    # STORAGE
    # ========================================================

    def total_size(
        self,
    ) -> int:
        return sum(path.stat().st_size for path in self.downloads())

    def show_storage(
        self,
    ) -> None:
        console.print(
            Panel.fit(
                format_size(self.total_size()),
                title="Storage Usage",
                border_style="cyan",
            )
        )

    # ========================================================
    # CLEAR DOWNLOADS
    # ========================================================

    def clear(
        self,
        videos: bool = True,
        audio: bool = True,
        force: bool = False,
    ) -> None:
        files: list[Path] = []

        if videos:
            files.extend(self.videos())

        if audio:
            files.extend(self.audios())

        if not files:
            console.print(("[yellow]Nothing to delete.[/yellow]"))
            return

        if not force:
            answer = console.input(
                (f"[yellow]Delete {len(files)} files? [y/N]: [/yellow]")
            )

            answer = answer.strip().lower()

            if answer not in {
                "y",
                "yes",
            }:
                console.print("[red]Cancelled.[/red]")
                return

        if videos:
            # Forget what was downloaded, or batch and playlist runs would skip it.
            for archive in self.download_dir.rglob(self.ARCHIVE_NAME):
                archive.unlink()

        for path in files:
            path.unlink()

            parent = path.parent
            while parent != self.download_dir and parent != self.audio_dir:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

        console.print((f"[green]Deleted {len(files)} files[/green]"))

    # ========================================================
    # OPEN DOWNLOAD FOLDER
    # ========================================================

    def reveal_folder(
        self,
    ) -> None:
        path = self.download_dir.resolve()

        if not open_folder(path):
            console.print(str(path))

    # ========================================================
    # BATCH DOWNLOAD
    # ========================================================

    def download_many(
        self,
        urls: list[str],
        compatible: bool = False,
        max_height: int | None = None,
        jobs: int = 1,
        skip_downloaded: bool = True,
    ) -> list[Path]:
        console.print(
            Panel.fit(
                (f"[bold]{len(urls)} videos queued[/bold]"
                 + (f" [dim]({jobs} at a time)[/dim]" if jobs > 1 else "")),
                title="Batch Download",
                border_style="blue",
            )
        )

        template = str(self.download_dir / self._output_name(None))
        downloaded, skipped, failed = self._download_entries(
            [(url, template) for url in urls],
            archive=self.download_dir / self.ARCHIVE_NAME if skip_downloaded else None,
            jobs=jobs,
            compatible=compatible,
            max_height=max_height,
        )

        summary = f"{len(downloaded)}/{len(urls)} downloaded"
        if skipped:
            summary += f", {skipped} already there"
        if failed:
            summary += f", {failed} failed"
        console.print(f"\n[green bold]Batch complete[/green bold]\n{summary}")

        return downloaded


def parse_browser(value: str | None) -> tuple | None:
    """Turn 'chrome' or 'chrome:Profile 1' into yt-dlp's cookiesfrombrowser tuple."""
    if not value or value.lower() == "none":
        return None
    browser, _, profile = value.partition(":")
    browser = browser.strip().lower()
    if browser not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"Unsupported browser '{browser}'. Choose one of: {', '.join(sorted(SUPPORTED_BROWSERS))}."
        )
    return (browser, profile.strip() or None, None, None)
