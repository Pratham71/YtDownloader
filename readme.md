# ytdl

> **A cross-platform CLI** for downloading YouTube videos, playlists, and MP3 audio from your terminal on Windows, macOS, and Linux.

Download the best resolution and frame rate available, search YouTube, grab whole playlists, or manage your local downloads. `ytdl` checks for new versions on its own and updates itself with one command.

## Features

| | |
| --- | --- |
| **Video** | Highest available resolution and frame rate by default; optional H.264/AAC MP4 mode or a height limit |
| **Audio** | Download straight to MP3, or keep the video and convert it |
| **Discover** | Show video information, search, and download a search result |
| **Playlists** | Download every video into a named folder with numbered filenames, or only the first N entries |
| **Manage** | Batch download, list files, show storage usage, open the download folder, and clear files |
| **Stay current** | Daily background update check, `ytdl update` to upgrade ytdl and yt-dlp, `ytdl doctor` to check your setup |

## Install

`ytdl` needs [FFmpeg](https://ffmpeg.org/download.html) and either [Node.js 22+](https://nodejs.org/en/download) or [Deno 2.3+](https://docs.deno.com/runtime/getting_started/installation/) on your `PATH`. The installers below set up [uv](https://docs.astral.sh/uv/) and Python for you.

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Pratham71/YtDownloader/main/scripts/install.ps1 | iex"
```

**macOS and Linux**:

```bash
curl -LsSf https://raw.githubusercontent.com/Pratham71/YtDownloader/main/scripts/install.sh | sh
```

Already have uv, or prefer pipx or pip? Any of these work:

```bash
uv tool install git+https://github.com/Pratham71/YtDownloader.git
pipx install git+https://github.com/Pratham71/YtDownloader.git
pip install git+https://github.com/Pratham71/YtDownloader.git
```

Open a new terminal, then run `ytdl doctor`. It checks for FFmpeg and a JavaScript runtime and prints the install command for your OS if one is missing:

| OS | FFmpeg | JavaScript runtime |
| --- | --- | --- |
| Windows | `winget install Gyan.FFmpeg` | `winget install OpenJS.NodeJS.LTS` |
| macOS | `brew install ffmpeg` | `brew install node` |
| Linux | `sudo apt-get install ffmpeg` (or your distro's package manager) | `curl -fsSL https://deno.land/install.sh \| sh` |

## Updating

`ytdl` checks GitHub and PyPI for new versions of itself and of [yt-dlp](https://github.com/yt-dlp/yt-dlp) at most once a day, in the background, and prints a short notice after a command when something newer is out. To update:

```bash
ytdl update            # upgrade ytdl and yt-dlp
ytdl update --check    # only show installed and latest versions
ytdl update --dry-run  # show the commands it would run
```

`ytdl update` detects how it was installed (uv, pipx, pip, or a git checkout) and runs the matching upgrade. On Windows, the upgrade runs in a new console window, because Windows cannot replace a program while it is running. If YouTube changes and downloads start failing, `ytdl update` is the first thing to try: it pulls in the newest yt-dlp.

Turn the background check off with `ytdl config set check-updates false`, or for one run with the environment variable `YTDL_NO_UPDATE_CHECK=1`.

## Download quality

With the built-in `best` setting, `download`, `playlist`, `grab`, and `batch` choose the **highest resolution available**, then the highest frame rate at that resolution. The final file is MP4 when its video and audio codecs fit that container, otherwise MKV. Some players may need newer codec support for the highest-quality formats.

Add `--compatible` to prefer H.264 video and AAC audio in an MP4. This can select a lower resolution when YouTube does not provide the highest resolution in H.264. Add `--best` to use the highest available quality for one run when your saved default is `compatible`.

```bash
ytdl download "https://www.youtube.com/watch?v=VIDEO_ID"
ytdl download "https://www.youtube.com/watch?v=VIDEO_ID" --compatible
ytdl download "https://www.youtube.com/watch?v=VIDEO_ID" --max-height 1080
```

`--max-height` is a ceiling, not a target: it picks the best available format at or below that height, and combines with `--compatible` or `--best`. Downloading the same URL again with the same filename may reuse the existing file; use `-o` with a new name when switching quality modes.

## Download a playlist

Pass a playlist link to `playlist`. Videos are saved in order into `<download folder>/<playlist name>/`, with names such as `001 - Video title.mp4`.

```bash
ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --first 3 --max-height 1080
```

Unavailable videos are skipped, so the number of files can be lower than the entry count. `list`, `storage`, and `clear` include playlist videos.

## Where files go

By default, videos go to `Downloads/ytdl` in your home folder and MP3 files to `Downloads/ytdl/mp3`. Change it for one run with `--dir` **before** the command, or save a new default:

```bash
ytdl --dir ./videos download "URL"
ytdl config set download-dir ~/Videos/youtube
```

## Save default settings

Settings live in `config.json`, created when you save your first setting:

| OS | Location |
| --- | --- |
| Windows | `%APPDATA%\ytdl\config.json` |
| macOS | `~/Library/Application Support/ytdl/config.json` |
| Linux | `$XDG_CONFIG_HOME/ytdl/config.json` (default `~/.config/ytdl/config.json`) |

Run `ytdl config path` to see the exact file, or set `YTDL_CONFIG_FILE` to use another one. Settings from the old `yt-downloader` config folder are moved over automatically the first time `ytdl` runs.

```bash
ytdl config show
ytdl config set download-dir "~/Videos"
ytdl config set quality compatible
ytdl config set keep-video true
ytdl config set check-updates false
ytdl config reset
```

| Setting | Values | Built-in default |
| --- | --- | --- |
| `download-dir` | Any folder; saved as an absolute path | `~/Downloads/ytdl` |
| `quality` | `best` or `compatible` | `best` |
| `keep-video` | `true` or `false` | `false` |
| `check-updates` | `true` or `false` | `true` |

A command-line option overrides a saved setting for that run: `--dir`, `--compatible` / `--best`, and `--keep-video` / `--delete-video`.

## All commands

| Command | What it does |
| --- | --- |
| `ytdl download "URL"` | Download a video with audio using the saved quality setting |
| `ytdl download "URL" -o "my-video.mp4"` | Choose an output name; the extension follows the actual container |
| `ytdl download "URL" --compatible` | Prefer an H.264/AAC MP4 |
| `ytdl download "URL" --max-height 1080` | Pick the best format up to 1080p |
| `ytdl playlist "PLAYLIST_URL"` | Download the whole playlist into its own folder |
| `ytdl playlist "PLAYLIST_URL" --first 3` | Download only the first three entries |
| `ytdl audio "URL"` | Download the audio only and save it as MP3 |
| `ytdl audio "URL" --keep-video` | Download the video too, then convert it to MP3 |
| `ytdl info "URL"` | Show title, channel, duration, views, and URL |
| `ytdl search WORDS -n 10` | Search YouTube; show ten results (default five) |
| `ytdl grab WORDS -i 2` | Download search result number two |
| `ytdl batch "URL1" "URL2"` | Download several videos |
| `ytdl list` | List downloaded video and audio files |
| `ytdl storage` | Show disk space used by downloads |
| `ytdl open` | Open the downloads folder in your file manager |
| `ytdl clear` | Delete downloads after confirmation (`--videos-only`, `--audio-only`, `-f`) |
| `ytdl config show` / `path` / `set` / `reset` | Manage saved defaults |
| `ytdl update` | Upgrade ytdl and yt-dlp (`--check`, `--dry-run`) |
| `ytdl doctor` | Check FFmpeg, the JavaScript runtime, and versions |
| `ytdl --version` | Print the installed version |

`--compatible`, `--best`, and `--max-height` work with `download`, `playlist`, `grab`, and `batch`. Use `ytdl --help` or `ytdl COMMAND --help` for built-in help.

## Development

```bash
git clone https://github.com/Pratham71/YtDownloader.git
cd YtDownloader
uv sync
uv run ytdl --help
uv run python -m unittest discover -s tests -t .
```

`uv run python -m ytdl` also works. Set `YT_DOWNLOAD_LIVE_TEST=1` to include the test that downloads a real video. In a git checkout, `ytdl update` runs `git pull --ff-only` and `uv sync --upgrade-package yt-dlp`.

### Releasing a new version

Installed copies learn about new versions from the `version` in `pyproject.toml` on the `main` branch, so a release is:

1. Raise `version` in `pyproject.toml` and run `uv lock`.
2. Add the changes to [CHANGELOG.md](CHANGELOG.md).
3. Commit and push to `main`. Optionally tag it, for example `git tag v0.3.0 && git push --tags`.

Within a day, everyone's `ytdl` shows a notice, and `ytdl update` installs the new version.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
