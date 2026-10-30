# ytdl

> **A cross-platform CLI** for downloading videos and audio from YouTube, TikTok, Instagram, X, Reddit, Vimeo, SoundCloud, and over a thousand other sites, on Windows, macOS, and Linux.

`ytdl` picks the best quality available, embeds titles, thumbnails, and subtitles, downloads several videos at once, skips what you already have, and keeps itself up to date. It is built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), the actively maintained successor to youtube-dl.

## Features

| | |
| --- | --- |
| **Any site** | YouTube, TikTok, Instagram (reels and multi-video posts), X, Reddit, Vimeo, SoundCloud, and more: run `ytdl sites` for the full list |
| **Quality** | Highest resolution and frame rate by default, an H.264/AAC MP4 mode that plays everywhere, a height limit, or a specific format picked from a list |
| **Audio** | Download straight to MP3, with title, artist, and cover art |
| **Extras** | Metadata, chapters, and thumbnails embedded by default; subtitles on request |
| **Many at once** | Batch and playlist downloads run in parallel, resume after interruptions, and skip videos already downloaded |
| **Logins** | Use your browser's login for sites that need one, such as Instagram |
| **Discover** | Show video information, search YouTube, and download a search result |
| **Manage** | List files, show storage usage, open the download folder, and clear files |
| **Stay current** | A daily background update check, `ytdl update`, and `ytdl doctor` to check your setup |

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

## Quick start

```bash
ytdl download "https://www.youtube.com/watch?v=VIDEO_ID"
ytdl download "https://www.tiktok.com/@user/video/VIDEO_ID"
ytdl download "https://www.instagram.com/reel/REEL_ID/"
ytdl audio "https://soundcloud.com/artist/track"
ytdl batch "URL1" "URL2" "URL3" -j 3
ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Files are saved in `Downloads/ytdl` in your home folder, named `Title [id].ext`. The ID keeps names unique, because many sites reuse titles such as "Video by instagram".

## Download quality

With the built-in `best` setting, ytdl chooses the **highest resolution available**, then the highest frame rate at that resolution. The file is MP4 when its video and audio fit that container, otherwise MKV.

Add `--compatible` to prefer H.264 video and AAC audio in an MP4, which plays on almost anything. This can select a lower resolution when the site does not offer the highest one in H.264. Use `ytdl config set quality compatible` to make it your default, and `--best` to override that for one run.

```bash
ytdl download "URL" --compatible
ytdl download "URL" --max-height 1080
```

`--max-height` is a ceiling, not a target: it picks the best format at or below that height and works with either quality mode.

### Pick a specific format

```bash
ytdl formats "URL"            # list every format: resolution, fps, codecs, size
ytdl download "URL" -f 137    # download format 137
ytdl download "URL" --choose  # show the list and ask which one
```

A video-only format is merged with the best audio automatically.

## Subtitles, metadata, and thumbnails

The title, channel, upload date, source URL, chapters, and thumbnail are embedded into every video and MP3. Turn this off for one run with `--no-metadata`, or always with `ytdl config set embed-metadata false`.

Add `--subs` to embed subtitles. On its own it embeds English; give languages to choose others. Auto-generated subtitles are used when a video has no human-made ones.

```bash
ytdl download "URL" --subs
ytdl download "URL" --subs en,es,fr
```

## Several videos at once

`batch` downloads a list of URLs, from the command line, a text file, or both. `-j` sets how many run at the same time (1 to 8):

```bash
ytdl batch "URL1" "URL2" -j 3
ytdl batch --file urls.txt -j 4
```

In the URL file, put one URL per line. Blank lines and lines starting with `#` are ignored. Save a default with `ytdl config set jobs 3`.

### Playlists, channels, and profiles

`playlist` downloads every video from a playlist, channel, or profile page into `<download folder>/<playlist name>/`, with names such as `001 - Video title [id].mp4`:

```bash
ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" -j 3
ytdl playlist "https://www.youtube.com/@channel/videos" --first 10
```

### Resume and skip

`batch` and `playlist` remember what they downloaded in each folder. Run the same command again, after an interruption or when a playlist gets new videos, and ytdl skips what is already there and downloads the rest. Interrupted downloads resume where they stopped. Add `--force` to download everything again. `ytdl clear` also clears this record, so cleared videos can be downloaded again.

A video that fails, for example because it was removed, is reported and the rest carry on. Press Ctrl+C to stop all running downloads.

## Sites that need a login

Instagram usually needs you to be logged in, and Vimeo, Reddit, X, and age-restricted YouTube videos sometimes do. Log in with your browser as normal, then let ytdl use that login:

```bash
ytdl --cookies-from-browser chrome download "URL"
ytdl config set cookies-from-browser chrome     # use it every time
```

Supported browsers are Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi, Chromium, and Whale. Add a profile name after a colon, such as `firefox:work`. You can also pass a Netscape-format `cookies.txt` file with `--cookies FILE`. When a download fails with a login error, ytdl suggests this.

If reading Chrome or Edge cookies fails on Windows, close the browser and try again, or log in with Firefox and use `--cookies-from-browser firefox`.

## Updating

`ytdl` checks GitHub and PyPI for new versions of itself and of yt-dlp at most once a day, in the background, and prints a short notice after a command when something newer is out.

```bash
ytdl update            # upgrade ytdl and yt-dlp
ytdl update --check    # only show installed and latest versions
ytdl update --dry-run  # show the commands it would run
```

`ytdl update` detects how it was installed (uv, pipx, pip, or a git checkout) and runs the matching upgrade. On Windows, the upgrade runs in a new console window, because Windows cannot replace a program while it is running. If a site changes and downloads start failing, `ytdl update` is the first thing to try.

Turn off the background check with `ytdl config set check-updates false`, or for one run with the environment variable `YTDL_NO_UPDATE_CHECK=1`.

## Settings

Settings live in `config.json`, created when you save your first setting:

| OS | Location |
| --- | --- |
| Windows | `%APPDATA%\ytdl\config.json` |
| macOS | `~/Library/Application Support/ytdl/config.json` |
| Linux | `$XDG_CONFIG_HOME/ytdl/config.json` (default `~/.config/ytdl/config.json`) |

Run `ytdl config path` to see the exact file, or set `YTDL_CONFIG_FILE` to use another one. Settings from the old `yt-downloader` config folder are moved over automatically.

```bash
ytdl config show
ytdl config set download-dir "~/Videos"
ytdl config reset
```

| Setting | Values | Built-in default |
| --- | --- | --- |
| `download-dir` | Any folder; saved as an absolute path | `~/Downloads/ytdl` |
| `quality` | `best` or `compatible` | `best` |
| `keep-video` | `true` or `false`: keep the video after `audio` makes an MP3 | `false` |
| `embed-metadata` | `true` or `false` | `true` |
| `cookies-from-browser` | A browser name, `browser:profile`, or `none` | `none` |
| `jobs` | `1` to `8` parallel downloads for `batch` and `playlist` | `1` |
| `check-updates` | `true` or `false` | `true` |

An option on the command line overrides the saved setting for that run.

## All commands

| Command | What it does |
| --- | --- |
| `ytdl download "URL"` | Download a video (options: `-o NAME`, `--compatible`, `--best`, `--max-height`, `--subs`, `-f ID`, `--choose`) |
| `ytdl audio "URL"` | Download the audio only and save it as MP3 (`--keep-video` also keeps the video) |
| `ytdl batch "URL" ... [-a FILE]` | Download several videos (`-j N`, `--force`, plus the quality options) |
| `ytdl playlist "URL"` | Download a playlist, channel, or profile into its own folder (`--first N`, `-j N`, `--force`) |
| `ytdl info "URL"` | Show title, channel, site, duration, and views |
| `ytdl formats "URL"` | List the available formats |
| `ytdl search WORDS [-n N]` | Search YouTube (results are cached for an hour) |
| `ytdl grab WORDS [-i N]` | Download search result number N, the same one `search` showed |
| `ytdl sites [FILTER]` | List supported sites |
| `ytdl list` | List downloaded video and audio files |
| `ytdl storage` | Show disk space used by downloads |
| `ytdl open` | Open the download folder in your file manager |
| `ytdl clear` | Delete downloads after confirmation (`--videos-only`, `--audio-only`, `-f`) |
| `ytdl config show` / `path` / `set` / `reset` | Manage settings |
| `ytdl update` | Upgrade ytdl and yt-dlp (`--check`, `--dry-run`) |
| `ytdl doctor` | Check FFmpeg, the JavaScript runtime, and versions |
| `ytdl --version` | Print the installed version |

These options go **before** the command and work with any of them:

| Option | What it does |
| --- | --- |
| `--dir PATH` | Use another download folder for this run |
| `--cookies-from-browser BROWSER` | Use your login from a browser |
| `--cookies FILE` | Use a `cookies.txt` file |
| `--no-metadata` | Do not embed metadata, chapters, or thumbnails |

Use `ytdl --help` or `ytdl COMMAND --help` for built-in help.

## Troubleshooting

| Problem | Try |
| --- | --- |
| Downloads suddenly fail on a site that used to work | `ytdl update`: sites change often, and yt-dlp is updated to keep up |
| "requires login", "rate-limit", or "confirm you're not a bot" | `--cookies-from-browser chrome` (see [Sites that need a login](#sites-that-need-a-login)) |
| "Nothing to download here" on an Instagram post | The post contains only images; ytdl downloads video and audio only |
| "Requested format is not available" | `ytdl formats URL`, then `-f ID`, or drop `--compatible` / `--max-height` |
| "FFmpeg was not found" | `ytdl doctor` shows the install command for your OS |
| A site cannot be reached at all | Check that it is not blocked on your network; ytdl cannot work around that |

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
