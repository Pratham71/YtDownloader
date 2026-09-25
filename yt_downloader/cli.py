import argparse

from rich.console import Console
from rich.panel import Panel

from .downloader import YTDownloader


console = Console()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdl",
        description=("A simple and clean YouTube downloader CLI."),
    )

    parser.add_argument(
        "--dir",
        default="downloads",
        help=("Download directory (default: downloads)"),
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

    download.add_argument(
        "--compatible",
        action="store_true",
        help="Prefer H.264 video and AAC audio in MP4",
    )

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

    audio.add_argument(
        "--keep-video",
        action="store_true",
        help=("Keep the MP4 after MP3 conversion"),
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

    grab.add_argument(
        "--compatible",
        action="store_true",
        help="Prefer H.264 video and AAC audio in MP4",
    )

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

    batch.add_argument(
        "--compatible",
        action="store_true",
        help="Prefer H.264 video and AAC audio in MP4",
    )

    return parser


def run_cli() -> None:
    parser = create_parser()

    args = parser.parse_args()

    downloader = YTDownloader(download_dir=args.dir)

    try:
        match args.command:
            case "download":
                downloader.download(
                    args.url,
                    filename=args.output,
                    compatible=args.compatible,
                )

            case "audio":
                downloader.download_mp3(
                    args.url,
                    delete_video=(not args.keep_video),
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
                    compatible=args.compatible,
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
                downloader.download_many(args.urls, compatible=args.compatible)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")

    except Exception as exc:
        console.print(
            Panel.fit(
                (f"[red bold]Error[/red bold]\n{exc}"),
                border_style="red",
            )
        )
