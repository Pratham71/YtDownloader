from __future__ import annotations

import os
import shutil
from pathlib import Path
from time import perf_counter

from moviepy import VideoFileClip
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch

from rich.console import Console
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

from .models import VideoInfo
from .utils import (
    ensure_extension,
    format_size,
    sanitize_filename,
)


console = Console()


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
    }

    def __init__(
        self,
        url: str | None = None,
        download_dir: str | Path = "downloads",
    ):
        self.url = url

        self.download_dir = Path(download_dir)
        self.audio_dir = self.download_dir / "mp3"

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
            raise ValueError("No YouTube URL was provided.")

        return final_url

    @staticmethod
    def _video_info(data: dict, url: str) -> VideoInfo:
        return VideoInfo(
            title=data.get("title") or data.get("id") or "Unknown",
            author=data.get("uploader") or data.get("channel") or "Unknown",
            duration_seconds=int(data.get("duration") or 0),
            views=data.get("view_count") or 0,
            url=data.get("webpage_url") or url,
        )

    @staticmethod
    def _ydl_options() -> dict:
        return {
            "noplaylist": True,
            "quiet": True,
            # Deno works by default; explicitly enable Node when it is installed.
            "js_runtimes": {"deno": {}, "node": {}},
        }

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

    def show_info(
        self,
        url: str | None = None,
    ) -> None:
        info = self.info(url)

        table = Table(
            title="YouTube Video",
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
            info.title,
        )

        table.add_row(
            "Channel",
            info.author,
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
            info.url,
        )

        console.print(table)

    # ========================================================
    # VIDEO DOWNLOAD
    # ========================================================

    def download(
        self,
        url: str | None = None,
        filename: str | None = None,
        compatible: bool = False,
    ) -> Path:
        final_url = self._require_url(url)

        progress_task = None

        if filename:
            filename = sanitize_filename(filename)
            suffix = Path(filename).suffix.lower()
            if suffix in self.VIDEO_EXTENSIONS:
                filename = filename[: -len(suffix)]
            output_name = filename.replace("%", "%%") + ".%(ext)s"
        else:
            output_name = "%(title).200B.%(ext)s"

        options = self._ydl_options()
        options.update(
            {
                "format": (
                    "bv[vcodec^=avc1][ext=mp4]+ba[ext=m4a]/"
                    "b[vcodec^=avc1][ext=mp4]"
                    if compatible else "bv+ba/b"
                ),
                "merge_output_format": "mp4" if compatible else "mp4/mkv",
                "outtmpl": str(self.download_dir / output_name),
                "progress_hooks": [],
                "noprogress": True,
            }
        )
        if not compatible:
            options["format_sort"] = ["res", "fps"]
            options["format_sort_force"] = True

        with Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:

            def on_progress(status: dict) -> None:
                nonlocal progress_task

                if status["status"] not in {"downloading", "finished"}:
                    return

                total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
                downloaded = status.get("downloaded_bytes") or total

                if progress_task is None:
                    progress_task = progress.add_task(
                        "Downloading",
                        total=total or None,
                    )

                progress.update(
                    progress_task,
                    total=total or None,
                    completed=downloaded,
                )

            options["progress_hooks"].append(on_progress)
            start = perf_counter()
            with YoutubeDL(options) as ydl:
                data = ydl.extract_info(final_url, download=True)
                downloads = data.get("requested_downloads") or []
                result = downloads[0].get("filepath") if downloads else None
                path = Path(result or ydl.prepare_filename(data))
            elapsed = perf_counter() - start

        info = self._video_info(data, final_url)
        height = data.get("height")
        fps = data.get("fps")
        quality = f"{height}p" if height else "Unknown resolution"
        if fps:
            quality += f" • {fps} fps"

        console.print(
            Panel.fit(
                (
                    f"[bold]{info.title}[/bold]\n"
                    f"[dim]{info.author} • {info.duration} • "
                    f"{info.readable_views} views[/dim]\n"
                    f"[cyan]{quality}[/cyan]"
                ),
                title="YouTube Video",
                border_style="cyan",
            )
        )

        console.print(
            Panel.fit(
                (
                    "[green bold]"
                    "✓ Download complete"
                    "[/green bold]\n"
                    f"{path.name}\n"
                    f"[dim]{elapsed:.2f}s[/dim]"
                ),
                border_style="green",
            )
        )

        return path

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

        console.print((f"\n[cyan]Converting:[/cyan] [bold]{video_path.name}[/bold]"))

        start = perf_counter()

        with VideoFileClip(str(video_path)) as video:
            if video.audio is None:
                raise ValueError("Video does not contain audio.")

            video.audio.write_audiofile(
                str(output_path),
                logger=None,
            )

        elapsed = perf_counter() - start

        if delete_video:
            video_path.unlink()

        console.print(
            Panel.fit(
                (
                    "[green bold]"
                    "✓ MP3 conversion complete"
                    "[/green bold]\n"
                    f"{output_path.name}\n"
                    f"[dim]{elapsed:.2f}s[/dim]"
                ),
                border_style="green",
            )
        )

        return output_path

    def download_mp3(
        self,
        url: str | None = None,
        delete_video: bool = True,
    ) -> Path:
        video = self.download(url, compatible=True)

        return self.to_mp3(
            video,
            delete_video=delete_video,
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @staticmethod
    def search(
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        results = VideosSearch(
            query,
            limit=limit,
        ).result()["result"]

        return [
            {
                "title": result["title"],
                "channel": result["channel"]["name"],
                "duration": result.get(
                    "duration",
                    "Unknown",
                ),
                "views": result.get(
                    "viewCount",
                    {},
                ).get(
                    "short",
                    "Unknown",
                ),
                "url": result["link"],
            }
            for result in results
        ]

    @classmethod
    def show_search(
        cls,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        results = cls.search(
            query,
            limit,
        )

        table = Table(
            title=f'Search: "{query}"',
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
                video["title"],
                video["channel"],
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
    ) -> Path:
        results = self.search(
            query,
            limit=max(index, 5),
        )

        if index < 1 or index > len(results):
            raise IndexError("Invalid search result index.")

        selected = results[index - 1]

        console.print((f"[cyan]Selected:[/cyan] [bold]{selected['title']}[/bold]"))

        return self.download(selected["url"], compatible=compatible)

    # ========================================================
    # DOWNLOADED FILES
    # ========================================================

    def videos(
        self,
    ) -> list[Path]:
        return sorted(
            path
            for path in self.download_dir.iterdir()
            if (path.is_file() and path.suffix.lower() in self.VIDEO_EXTENSIONS)
        )

    def audios(
        self,
    ) -> list[Path]:
        return sorted(
            path
            for path in self.audio_dir.iterdir()
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
                path.name,
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

        for path in files:
            path.unlink()

        console.print((f"[green]✓ Deleted {len(files)} files[/green]"))

    # ========================================================
    # OPEN DOWNLOAD FOLDER
    # ========================================================

    def reveal_folder(
        self,
    ) -> None:
        path = self.download_dir.resolve()

        if os.name == "nt":
            os.startfile(path)

        elif shutil.which("open"):
            os.system(f'open "{path}"')

        elif shutil.which("xdg-open"):
            os.system(f'xdg-open "{path}"')

        else:
            console.print(str(path))

    # ========================================================
    # BATCH DOWNLOAD
    # ========================================================

    def download_many(
        self,
        urls: list[str],
        continue_on_error: bool = True,
        compatible: bool = False,
    ) -> list[Path]:
        downloaded: list[Path] = []

        console.print(
            Panel.fit(
                (f"[bold]{len(urls)} videos queued[/bold]"),
                title="Batch Download",
                border_style="blue",
            )
        )

        for index, url in enumerate(
            urls,
            start=1,
        ):
            console.rule((f"[bold cyan]{index}/{len(urls)}[/bold cyan]"))

            try:
                path = self.download(url, compatible=compatible)

                downloaded.append(path)

            except Exception as exc:
                console.print((f"[red]✗ {exc}[/red]"))

                if not continue_on_error:
                    raise

        console.print(
            (
                "\n[green bold]"
                "Batch complete"
                "[/green bold]\n"
                f"{len(downloaded)}/"
                f"{len(urls)} downloaded"
            )
        )

        return downloaded
