import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import system, updater
from .config import MAX_JOBS, Settings, config_path, load_settings, save_settings
from .downloader import YTDownloader, clean_error, parse_browser


console = Console()
error_console = Console(stderr=True)

URL_HELP = "Video URL from YouTube, TikTok, Instagram, X, Reddit, Vimeo, or another supported site"
LOGIN_HINTS = re.compile(r"log ?in|sign in|cookies|private|rate.?limit|confirm you.re not a bot", re.I)


def parse_bool(value: str, name: str) -> bool:
    if value.lower() not in {"true", "false"}:
        raise ValueError(f"{name} must be 'true' or 'false'.")
    return value.lower() == "true"


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Enter a positive whole number.") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Enter a positive whole number.")
    return number


def job_count(value: str) -> int:
    number = positive_int(value)
    if number > MAX_JOBS:
        raise argparse.ArgumentTypeError(f"Use at most {MAX_JOBS} parallel downloads.")
    return number


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
    command.add_argument(
        "--max-height",
        type=positive_int,
        metavar="PIXELS",
        help="Limit video height while choosing the best available format",
    )
    command.add_argument(
        "--subs",
        nargs="?",
        const="en.*",
        metavar="LANGS",
        help="Embed subtitles, e.g. 'en' or 'en,es' (default with no value: English)",
    )


def add_many_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "-j",
        "--jobs",
        type=job_count,
        metavar="N",
        help=f"Download up to N videos at once (1-{MAX_JOBS}; default: saved jobs setting)",
    )
    command.add_argument(
        "--force",
        action="store_true",
        help="Download again even if a video was downloaded here before",
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
        return replace(settings, keep_video=parse_bool(value, "Keep-video"))
    if key == "check-updates":
        return replace(settings, check_updates=parse_bool(value, "Check-updates"))
    if key == "embed-metadata":
        return replace(settings, embed_metadata=parse_bool(value, "Embed-metadata"))
    if key == "cookies-from-browser":
        parse_browser(value)
        return replace(
            settings, cookies_from_browser=None if value.lower() == "none" else value
        )
    if key == "jobs":
        try:
            return replace(settings, jobs=job_count(value))
        except argparse.ArgumentTypeError as exc:
            raise ValueError(f"Jobs: {exc}") from exc
    raise ValueError(f"Unknown setting: {key}")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdl",
        description=(
            "Download videos and audio from YouTube, TikTok, Instagram, "
            "and over a thousand other sites."
        ),
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"ytdl {updater.current_version()}",
    )

    parser.add_argument(
        "--dir",
        help="Download directory for this run (overrides config)",
    )

    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER[:PROFILE]",
        help="Use your login from a browser, e.g. chrome, firefox, edge, safari",
    )

    parser.add_argument(
        "--cookies",
        metavar="FILE",
        help="Use cookies from a Netscape-format cookies.txt file",
    )

    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not embed title, channel, chapters, and thumbnail into files",
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
        help=URL_HELP,
    )

    download.add_argument(
        "-o",
        "--output",
        help="Custom filename",
    )

    add_quality_options(download)

    pick = download.add_mutually_exclusive_group()
    pick.add_argument(
        "-f",
        "--format",
        dest="format_id",
        metavar="ID",
        help="Download a specific format ID from `ytdl formats URL`",
    )
    pick.add_argument(
        "--choose",
        action="store_true",
        help="List the available formats and pick one",
    )

    playlist = subparsers.add_parser(
        "playlist",
        help="Download every video in a playlist or channel into a named folder",
    )
    playlist.add_argument("url", help="Playlist, channel, or profile URL")
    add_quality_options(playlist)
    add_many_options(playlist)
    playlist.add_argument(
        "--first",
        type=positive_int,
        metavar="COUNT",
        help="Download only the first COUNT playlist entries",
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
        help=URL_HELP,
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
    # INFO / FORMATS / SITES
    # ========================================================

    info = subparsers.add_parser(
        "info",
        help=("Display video information"),
    )

    info.add_argument(
        "url",
        help=URL_HELP,
    )

    formats = subparsers.add_parser(
        "formats",
        help="List the qualities and formats available for a video",
    )
    formats.add_argument("url", help=URL_HELP)

    sites = subparsers.add_parser(
        "sites",
        help="List supported websites",
    )
    sites.add_argument("filter", nargs="?", help="Only show sites whose name contains this text")

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
        type=positive_int,
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
        type=positive_int,
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
        nargs="*",
        help="Video URLs",
    )

    batch.add_argument(
        "-a",
        "--file",
        metavar="FILE",
        help="Read URLs from a text file, one per line ('#' starts a comment)",
    )

    add_quality_options(batch)
    add_many_options(batch)

    config = subparsers.add_parser("config", help="Manage saved CLI defaults")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="Show current settings and file location")
    config_commands.add_parser("path", help="Show the config file location")
    set_command = config_commands.add_parser("set", help="Save a default value")
    set_command.add_argument(
        "key",
        choices=[
            "download-dir", "quality", "keep-video", "check-updates",
            "cookies-from-browser", "embed-metadata", "jobs",
        ],
    )
    set_command.add_argument("value")
    config_commands.add_parser("reset", help="Restore all built-in defaults")

    # ========================================================
    # UPDATE / DOCTOR
    # ========================================================

    update = subparsers.add_parser(
        "update",
        help="Update ytdl and yt-dlp to the newest versions",
    )
    update.add_argument(
        "--check",
        action="store_true",
        help="Only check whether updates are available",
    )
    update.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the update commands without running them",
    )

    subparsers.add_parser(
        "doctor",
        help="Check that FFmpeg and a JavaScript runtime are installed",
    )

    return parser


def make_downloader(args: argparse.Namespace, settings: Settings) -> YTDownloader:
    return YTDownloader(
        download_dir=args.dir or settings.download_dir,
        cookies_from_browser=args.cookies_from_browser or settings.cookies_from_browser,
        cookie_file=args.cookies,
        embed_metadata=settings.embed_metadata and not args.no_metadata,
        subtitles=getattr(args, "subs", None),
    )


def read_url_file(path: str) -> list[str]:
    lines = Path(path).expanduser().read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def show_update_status(status: updater.UpdateStatus) -> None:
    table = Table(title="Updates", border_style="cyan")
    table.add_column("Package", style="bold cyan")
    table.add_column("Installed")
    table.add_column("Latest")
    table.add_column("Status")
    for name, current, latest, outdated in (
        ("ytdl", status.current, status.latest, status.ytdl_outdated),
        ("yt-dlp", status.yt_dlp_current, status.yt_dlp_latest, status.yt_dlp_outdated),
    ):
        if latest is None:
            state = "[yellow]could not check[/yellow]"
        elif outdated:
            state = "[yellow]update available[/yellow]"
        else:
            state = "[green]up to date[/green]"
        table.add_row(name, current, latest or "?", state)
    console.print(table)


def run_update(check_only: bool, dry_run: bool) -> None:
    status = updater.check_for_updates()
    show_update_status(status)
    if check_only:
        if status.ytdl_outdated or status.yt_dlp_outdated:
            console.print("Run [bold]ytdl update[/bold] to install the updates.")
        return

    method = updater.install_method()
    commands = updater.update_commands(method)
    console.print(f"[dim]Installed with: {method}[/dim]")
    for command in commands:
        console.print(f"[dim]$ {subprocess.list2cmdline(command)}[/dim]")
    if dry_run:
        return

    if updater.run_update(commands, method):
        console.print("[green bold]ytdl is up to date.[/green bold]")
    else:
        console.print(
            "[cyan]The update is running in a new window. "
            "ytdl will be ready to use when it finishes.[/cyan]"
        )


def run_doctor(settings: Settings, download_dir: str) -> None:
    table = Table(title="ytdl doctor", show_header=False, border_style="cyan")
    table.add_column("Check", style="bold cyan")
    table.add_column("Result")
    problems = []

    table.add_row("System", system.platform_label())
    table.add_row("Python", sys.version.split()[0])
    table.add_row("ytdl", updater.current_version())
    table.add_row("yt-dlp", updater.installed_version("yt-dlp"))
    table.add_row("Installed with", updater.install_method())

    for tool in ("ffmpeg", "ffprobe"):
        found = system.tool_version(tool)
        table.add_row(tool, found or "[red]missing[/red]")
        if not found:
            problems.append(f"Install FFmpeg (includes ffprobe): {system.install_hint('ffmpeg')}")

    runtimes = [(name, system.tool_version(name)) for name in ("deno", "node")]
    found_runtimes = [f"{name} {found}" for name, found in runtimes if found]
    table.add_row("JavaScript runtime", ", ".join(found_runtimes) or "[red]missing[/red]")
    if not found_runtimes:
        problems.append(f"Install Node.js 22+ or Deno 2.3+: {system.install_hint('javascript')}")

    folder = Path(download_dir).expanduser()
    table.add_row("Download folder", str(folder))
    table.add_row("Config file", str(config_path()))
    table.add_row("Browser cookies", settings.cookies_from_browser or "off")
    table.add_row("Update checks", "on" if settings.check_updates else "off")
    console.print(table)

    for problem in dict.fromkeys(problems):
        console.print(f"[yellow]- {problem}[/yellow]")
    if problems:
        raise SystemExit(1)
    console.print("[green bold]Everything ytdl needs is installed.[/green bold]")


def show_sites(match: str | None) -> None:
    names = YTDownloader.supported_sites(match)
    if not names:
        console.print(f"[yellow]No supported site matches '{match}'.[/yellow]")
        return
    console.print(Columns(names, column_first=True, padding=(0, 2)))
    console.print(
        f"[dim]{len(names)} sites. Most other pages with an embedded video work too.[/dim]"
    )


def error_message(exc: Exception) -> str:
    message = clean_error(exc)
    if LOGIN_HINTS.search(message):
        message += (
            "\n\n[yellow]This site may need you to be logged in. Log in with your browser, then run:[/yellow]\n"
            "  ytdl --cookies-from-browser chrome download URL\n"
            "[dim]Use firefox, edge, safari, brave, etc. as needed. "
            "Save it with: ytdl config set cookies-from-browser chrome[/dim]"
        )
    return message


def run_cli(argv: list[str] | None = None) -> None:
    # Some Windows terminals use cp1252. Replace unsupported glyphs rather
    # than failing after a download has already completed.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = create_parser()

    args = parser.parse_args(argv)
    update_check: updater.BackgroundCheck | None = None

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

        if args.command == "update":
            run_update(check_only=args.check, dry_run=args.dry_run)
            return
        if args.command == "doctor":
            run_doctor(settings, args.dir or settings.download_dir)
            return
        if args.command == "sites":
            show_sites(args.filter)
            return

        if settings.check_updates and not updater.update_checks_disabled():
            update_check = updater.BackgroundCheck()

        downloader = make_downloader(args, settings)
        compatible = False
        if args.command in {"download", "playlist", "grab", "batch"}:
            compatible = (args.quality_override or settings.quality) == "compatible"
        jobs = getattr(args, "jobs", None) or settings.jobs

        match args.command:
            case "download":
                format_id = args.format_id
                if args.choose:
                    format_id = downloader.choose_format(args.url)
                downloader.download(
                    args.url,
                    filename=args.output,
                    compatible=compatible,
                    max_height=args.max_height,
                    format_id=format_id,
                )

            case "playlist":
                downloader.download_playlist(
                    args.url,
                    compatible=compatible,
                    max_height=args.max_height,
                    first=args.first,
                    jobs=jobs,
                    skip_downloaded=not args.force,
                )

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

            case "formats":
                downloader.show_formats(args.url)

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
                    max_height=args.max_height,
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
                urls = list(args.urls)
                if args.file:
                    urls += read_url_file(args.file)
                if not urls:
                    raise ValueError("Give at least one URL, or a file of URLs with --file.")
                downloader.download_many(
                    urls,
                    compatible=compatible,
                    max_height=args.max_height,
                    jobs=jobs,
                    skip_downloaded=not args.force,
                )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")

    except Exception as exc:
        console.print(
            Panel.fit(
                (f"[red bold]Error[/red bold]\n{error_message(exc)}"),
                border_style="red",
            )
        )
        raise SystemExit(1) from exc

    finally:
        if update_check is not None:
            for notice in update_check.notices():
                error_console.print(f"[yellow]{notice}[/yellow]")
