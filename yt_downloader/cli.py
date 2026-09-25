import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .config import Settings, config_path, load_settings, save_settings
from .downloader import YTDownloader


console = Console()


def add_quality_options(command: argparse.ArgumentParser) -> None:
    quality = command.add_mutually_exclusive_group()
    quality.add_argument(
        "--compatible",
        dest="quality_override",
        action="store_const",
        const="compatible",
        help="Prefer H.264 video and AAC audio in MP4",
    )
    quality.add_argument(
        "--best",
        dest="quality_override",
        action="store_const",
        const="best",
        help="Use highest available quality for this run",
    )


def update_setting(settings: Settings, key: str, value: str) -> Settings:
    if key == "download-dir":
        if not value.strip():
            raise ValueError("Download directory cannot be empty.")
        return replace(settings, download_dir=str(Path(value).expanduser().resolve()))
    if key == "quality":
        if value not in {"best", "compatible"}:
            raise ValueError("Quality must be 'best' or 'compatible'.")
        return replace(settings, quality=value)
    if key == "keep-video":
        if value.lower() not in {"true", "false"}:
            raise ValueError("Keep-video must be 'true' or 'false'.")
        return replace(settings, keep_video=value.lower() == "true")
    raise ValueError(f"Unknown setting: {key}")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-downloader",
        description=("A simple and clean YouTube downloader CLI."),
    )

    parser.add_argument(
        "--dir",
        help="Download directory for this run (overrides config)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # ========================================================
    # DOWNLOAD
    # ========================================================

    download = subparsers.add_parser(
        "download",
        help="Download a video",
    )

    download.add_argument(
        "url",
        help="YouTube video URL",
    )

    download.add_argument(
        "-o",
        "--output",
        help="Custom filename",
    )

    add_quality_options(download)

    playlist = subparsers.add_parser(
        "playlist",
        help="Download every video in a playlist into a named folder",
    )
    playlist.add_argument("url", help="YouTube playlist URL")
    add_quality_options(playlist)

    # ========================================================
    # AUDIO
    # ========================================================

    audio = subparsers.add_parser(
        "audio",
        help=("Download and convert a video to MP3"),
    )

    audio.add_argument(
        "url",
        help="YouTube video URL",
    )

    keep_video = audio.add_mutually_exclusive_group()
    keep_video.add_argument(
        "--keep-video",
        dest="keep_video_override",
        action="store_const",
        const=True,
        help="Keep the video after MP3 conversion",
    )
    keep_video.add_argument(
        "--delete-video",
        dest="keep_video_override",
        action="store_const",
        const=False,
        help="Delete the video after MP3 conversion",
    )

    # ========================================================
    # INFO
    # ========================================================

    info = subparsers.add_parser(
        "info",
        help=("Display video information"),
    )

    info.add_argument(
        "url",
        help="YouTube video URL",
    )

    # ========================================================
    # SEARCH
    # ========================================================

    search = subparsers.add_parser(
        "search",
        help="Search YouTube",
    )

    search.add_argument(
        "query",
        nargs="+",
        help="Search query",
    )

    search.add_argument(
        "-n",
        "--limit",
        type=int,
        default=5,
        help=("Number of search results (default: 5)"),
    )

    # ========================================================
    # SEARCH + DOWNLOAD
    # ========================================================

    grab = subparsers.add_parser(
        "grab",
        help=("Search and download a result"),
    )

    grab.add_argument(
        "query",
        nargs="+",
        help="Search query",
    )

    grab.add_argument(
        "-i",
        "--index",
        type=int,
        default=1,
        help=("Result number to download (default: 1)"),
    )

    add_quality_options(grab)

    # ========================================================
    # LIST
    # ========================================================

    subparsers.add_parser(
        "list",
        help="List downloaded files",
    )

    # ========================================================
    # STORAGE
    # ========================================================

    subparsers.add_parser(
        "storage",
        help="Show storage usage",
    )

    # ========================================================
    # OPEN DIRECTORY
    # ========================================================

    subparsers.add_parser(
        "open",
        help=("Open downloads directory"),
    )

    # ========================================================
    # CLEAR
    # ========================================================

    clear = subparsers.add_parser(
        "clear",
        help=("Delete downloaded files"),
    )

    clear.add_argument(
        "--videos-only",
        action="store_true",
        help="Delete videos only",
    )

    clear.add_argument(
        "--audio-only",
        action="store_true",
        help="Delete audio only",
    )

    clear.add_argument(
        "-f",
        "--force",
        action="store_true",
        help=("Skip confirmation prompt"),
    )

    # ========================================================
    # BATCH
    # ========================================================

    batch = subparsers.add_parser(
        "batch",
        help=("Download multiple URLs"),
    )

    batch.add_argument(
        "urls",
        nargs="+",
        help="YouTube URLs",
    )

    add_quality_options(batch)

    config = subparsers.add_parser("config", help="Manage saved CLI defaults")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="Show current settings and file location")
    config_commands.add_parser("path", help="Show the config file location")
    set_command = config_commands.add_parser("set", help="Save a default value")
    set_command.add_argument("key", choices=["download-dir", "quality", "keep-video"])
    set_command.add_argument("value")
    config_commands.add_parser("reset", help="Restore all built-in defaults")

    return parser


def run_cli(argv: list[str] | None = None) -> None:
    parser = create_parser()

    args = parser.parse_args(argv)

    try:
        if args.command == "config" and args.config_command == "path":
            console.print(str(config_path()))
            return
        if args.command == "config" and args.config_command == "reset":
            config_path().unlink(missing_ok=True)
            console.print("Restored built-in defaults.")
            return

        settings = load_settings()
        if args.command == "config":
            match args.config_command:
                case "show":
                    console.print(f"Config file: {config_path()}")
                    console.print(json.dumps(asdict(settings), indent=2))
                case "set":
                    save_settings(update_setting(settings, args.key, args.value))
                    console.print(f"Saved {args.key} in {config_path()}")
            return

        downloader = YTDownloader(download_dir=args.dir or settings.download_dir)
        compatible = False
        if args.command in {"download", "playlist", "grab", "batch"}:
            compatible = (args.quality_override or settings.quality) == "compatible"

        match args.command:
            case "download":
                downloader.download(
                    args.url,
                    filename=args.output,
                    compatible=compatible,
                )

            case "playlist":
                downloader.download_playlist(args.url, compatible=compatible)

            case "audio":
                downloader.download_mp3(
                    args.url,
                    delete_video=not (
                        settings.keep_video
                        if args.keep_video_override is None
                        else args.keep_video_override
                    ),
                )

            case "info":
                downloader.show_info(args.url)

            case "search":
                query = " ".join(args.query)

                downloader.show_search(
                    query,
                    limit=args.limit,
                )

            case "grab":
                query = " ".join(args.query)

                downloader.download_search_result(
                    query,
                    index=args.index,
                    compatible=compatible,
                )

            case "list":
                downloader.show_downloads()

            case "storage":
                downloader.show_storage()

            case "clear":
                videos = True
                audio = True

                if args.videos_only:
                    audio = False

                if args.audio_only:
                    videos = False

                downloader.clear(
                    videos=videos,
                    audio=audio,
                    force=args.force,
                )

            case "open":
                downloader.reveal_folder()

            case "batch":
                downloader.download_many(args.urls, compatible=compatible)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")

    except Exception as exc:
        console.print(
            Panel.fit(
                (f"[red bold]Error[/red bold]\n{exc}"),
                border_style="red",
            )
        )
        raise SystemExit(1) from exc
