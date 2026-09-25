
# YT Downloader

> **A CLI-only app** for downloading YouTube videos and MP3 audio from your terminal. There is no graphical or web interface.

Download the best resolution and frame rate available for a video, inspect its details, search YouTube, or manage your local downloads. Video and audio streams are merged with FFmpeg.

## Features

| | |
| --- | --- |
| **Video** | Highest available resolution and frame rate by default; optional H.264/AAC MP4 mode for broader compatibility |
| **Audio** | Download and convert to MP3, with an option to keep the video |
| **Discover** | Show video information, search, and download a search result |
| **Playlists** | Download every video into a folder named after the playlist, with numbered filenames |
| **Manage** | Batch download, list files, show storage usage, open the download folder, and clear files |

## Install

You need Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), [FFmpeg and ffprobe](https://ffmpeg.org/download.html), and either [Node.js 22+](https://nodejs.org/en/download) or [Deno 2.3+](https://docs.deno.com/runtime/getting_started/installation/). Make sure the FFmpeg tools and JavaScript runtime are on your `PATH`.

From the repository folder:

```powershell
uv sync
uv run ytdl --help
```

You can also start the same CLI through `main.py`, for example `uv run python main.py download "URL"`.

## Download quality

With the built-in `best` setting, `download`, `playlist`, `grab`, and `batch` choose the **highest resolution available**, then the highest frame rate at that resolution. If the source offers 1080p at 30 or 60 fps, that quality is eligible; a lower-resolution source cannot be made 1080p. The final file is MP4 when its video and audio codecs fit that container, otherwise MKV. Some players may need newer codec support for the highest-quality formats.

Add `--compatible` to prefer H.264 video and AAC audio in an MP4. This can select a lower resolution when YouTube does not provide the highest resolution in H.264. Add `--best` to use the highest available quality for one run when your saved default is `compatible`.

```powershell
uv run ytdl download "https://www.youtube.com/watch?v=VIDEO_ID"
uv run ytdl download "https://www.youtube.com/watch?v=VIDEO_ID" --compatible
```

The completed video download shows the selected resolution and frame rate. Downloading the same URL again with the same filename may reuse the existing file; use `-o` with a new name when switching quality modes.

## Download a playlist

Pass a YouTube playlist link to `playlist`. The app downloads its videos in order into `downloads/<playlist name>/`, with names such as `001 - Video title.mp4`. Invalid folder characters are replaced for your operating system. You can choose another base folder with `--dir`.

```powershell
uv run ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
uv run ytdl playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --compatible
```

Unavailable videos are skipped so the rest of the playlist can finish. The `list`, `storage`, and `clear` commands include downloaded playlist videos.

## Save default settings

The CLI reads `config.json` from `%APPDATA%\yt-downloader\` on Windows, or `$XDG_CONFIG_HOME/yt-downloader/` on Linux and macOS (falling back to `~/.config/yt-downloader/`). The file is created when you save your first setting. Run `uv run ytdl config path` to see its exact location. You can also set `YTDL_CONFIG_FILE` to use another JSON file.

```powershell
uv run ytdl config show
uv run ytdl config set download-dir "C:\Videos"
uv run ytdl config set quality compatible
uv run ytdl config set keep-video true
uv run ytdl config reset
```

`quality` accepts `best` or `compatible`; `keep-video` accepts `true` or `false`. Built-in defaults are `downloads`, `best`, and `false`. The saved download directory is stored as an absolute path, so it stays the same when you run `ytdl` from another folder. A command-line option overrides a saved setting for that run: use `--dir` before the command, `--compatible` or `--best` for video commands, and `--keep-video` or `--delete-video` for `audio`. The MP3 command always uses a compatible intermediate video for conversion.

## All CLI commands

Replace `URL` with a YouTube video link, `PLAYLIST_URL` with a playlist link, and `WORDS` with search terms. Commands below run from the repository folder.

| Command | What it does |
| --- | --- |
| `uv run ytdl download "URL"` | Download a video with audio using the saved quality setting |
| `uv run ytdl download "URL" -o "my-video.mp4"` | Choose an output name; the extension follows the actual container |
| `uv run ytdl download "URL" --compatible` | Prefer an H.264/AAC MP4 |
| `uv run ytdl download "URL" --best` | Use the highest quality for this run |
| `uv run ytdl playlist "PLAYLIST_URL"` | Download the whole playlist into its own named folder |
| `uv run ytdl playlist "PLAYLIST_URL" --compatible` | Download the playlist as compatible MP4 files |
| `uv run ytdl playlist "PLAYLIST_URL" --best` | Use the highest quality for this playlist |
| `uv run ytdl audio "URL"` | Download and convert to MP3; remove the temporary video |
| `uv run ytdl audio "URL" --keep-video` | Also keep the video used for conversion |
| `uv run ytdl audio "URL" --delete-video` | Delete the source video even when the saved default keeps it |
| `uv run ytdl info "URL"` | Show title, channel, duration, views, and URL |
| `uv run ytdl search WORDS` | Search YouTube; show five results |
| `uv run ytdl search WORDS -n 10` | Show ten search results |
| `uv run ytdl grab WORDS -i 2` | Download search result number two |
| `uv run ytdl grab WORDS -i 2 --compatible` | Download that result as a compatible MP4 |
| `uv run ytdl grab WORDS -i 2 --best` | Download that result at highest available quality |
| `uv run ytdl batch "URL1" "URL2"` | Download several videos |
| `uv run ytdl batch "URL1" "URL2" --compatible` | Batch download compatible MP4 files |
| `uv run ytdl batch "URL1" "URL2" --best` | Batch download at highest available quality |
| `uv run ytdl list` | List downloaded video and audio files |
| `uv run ytdl storage` | Show disk space used by downloads |
| `uv run ytdl open` | Open the downloads folder |
| `uv run ytdl clear` | Delete downloads after confirmation |
| `uv run ytdl clear --videos-only` | Delete only videos |
| `uv run ytdl clear --audio-only` | Delete only audio files |
| `uv run ytdl clear -f` | Delete without a confirmation prompt |
| `uv run ytdl config show` | Show saved or built-in defaults |
| `uv run ytdl config path` | Show the JSON config file location |
| `uv run ytdl config set download-dir "PATH"` | Save the default download folder |
| `uv run ytdl config set quality best` | Save `best` quality (or use `compatible`) |
| `uv run ytdl config set keep-video true` | Keep videos after MP3 conversion by default |
| `uv run ytdl config reset` | Remove saved settings and restore built-in defaults |

Use `--dir` **before** a command to choose another download folder for one run:

```powershell
uv run ytdl --dir "C:\Videos" download "URL"
```

Use `uv run ytdl --help` or `uv run ytdl download --help` for built-in help. By default, videos go in `downloads/` and MP3 files go in `downloads/mp3/`.

## Run `ytdl` from anywhere

Yes, you can add this CLI to your user `PATH`. From the repository folder, install its command with uv:

```powershell
uv tool install .
uv tool update-shell
```

Open a new terminal, then run `ytdl --help` or `ytdl download "URL"` from any directory. `uv tool update-shell` adds uv's tool executable directory to your user `PATH`. FFmpeg and Node.js or Deno still need to be available on `PATH`. To pick up later project changes, reinstall with `uv tool install --force .`.

## Updating

If YouTube changes and downloads stop working, update the extractor and sync the environment:

```powershell
uv lock --upgrade-package yt-dlp
uv sync
```

## License

[MIT](LICENSE)
