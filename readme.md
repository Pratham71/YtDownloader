# yt-downloader

> **A CLI-only app** for downloading YouTube videos and MP3 audio from your terminal. There is no graphical or web interface.

Download the best resolution and frame rate available for a video, inspect its details, search YouTube, or manage your local downloads. Video and audio streams are merged with FFmpeg.

## Features

| | |
| --- | --- |
| **Video** | Highest available resolution and frame rate by default; optional H.264/AAC MP4 mode or a height limit |
| **Audio** | Download and convert to MP3, with an option to keep the video |
| **Discover** | Show video information, search, and download a search result |
| **Playlists** | Download every video into a named folder with numbered filenames, or choose the first N entries |
| **Manage** | Batch download, list files, show storage usage, open the download folder, and clear files |

## Install

You need Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), [FFmpeg and ffprobe](https://ffmpeg.org/download.html), and either [Node.js 22+](https://nodejs.org/en/download) or [Deno 2.3+](https://docs.deno.com/runtime/getting_started/installation/). Make sure the FFmpeg tools and JavaScript runtime are on your `PATH`.

From the repository folder:

```powershell
uv sync
uv run yt-downloader --help
```

You can also run the Python module or `main.py` directly:

```powershell
uv run python -m yt_downloader download "URL"
uv run python main.py download "URL"
```

Python module names use underscores, so `yt_downloader` is the module name while `yt-downloader` is the terminal command.

## Download quality

With the built-in `best` setting, `download`, `playlist`, `grab`, and `batch` choose the **highest resolution available**, then the highest frame rate at that resolution. If the source offers 1080p at 30 or 60 fps, that quality is eligible; a lower-resolution source cannot be made 1080p. The final file is MP4 when its video and audio codecs fit that container, otherwise MKV. Some players may need newer codec support for the highest-quality formats.

Add `--compatible` to prefer H.264 video and AAC audio in an MP4. This can select a lower resolution when YouTube does not provide the highest resolution in H.264. Add `--best` to use the highest available quality for one run when your saved default is `compatible`.

```powershell
uv run yt-downloader download "https://www.youtube.com/watch?v=VIDEO_ID"
uv run yt-downloader download "https://www.youtube.com/watch?v=VIDEO_ID" --compatible
uv run yt-downloader download "https://www.youtube.com/watch?v=VIDEO_ID" --max-height 1080
```

`--max-height` is an optional ceiling, not a target: it picks the best available format at or below that height. It can be combined with `--compatible` or `--best`. If the source has no matching format below the ceiling, the download fails. The completed video download shows the selected resolution and frame rate. Downloading the same URL again with the same filename may reuse the existing file; use `-o` with a new name when switching quality modes.

## Download a playlist

Pass a YouTube playlist link to `playlist`. The app downloads its videos in order into `downloads/<playlist name>/`, with names such as `001 - Video title.mp4`. Invalid folder characters are replaced for your operating system. You can choose another base folder with `--dir`.

```powershell
uv run yt-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
uv run yt-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --compatible
uv run yt-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --first 3 --max-height 1080
```

`--first 3` processes the first three playlist entries; omit it to download the whole playlist. Unavailable videos are skipped, so the number of files can be lower than the requested entry count. The `list`, `storage`, and `clear` commands include downloaded playlist videos.

## Save default settings

The CLI reads `config.json` from `%APPDATA%\yt-downloader\` on Windows, or `$XDG_CONFIG_HOME/yt-downloader/` on Linux and macOS (falling back to `~/.config/yt-downloader/`). The file is created when you save your first setting. Run `uv run yt-downloader config path` to see its exact location. You can also set `YT_DOWNLOADER_CONFIG_FILE` to use another JSON file.

```powershell
uv run yt-downloader config show
uv run yt-downloader config set download-dir "C:\Videos"
uv run yt-downloader config set quality compatible
uv run yt-downloader config set keep-video true
uv run yt-downloader config reset
```

`quality` accepts `best` or `compatible`; `keep-video` accepts `true` or `false`. Built-in defaults are `downloads`, `best`, and `false`. The saved download directory is stored as an absolute path, so it stays the same when you run `yt-downloader` from another folder. A command-line option overrides a saved setting for that run: use `--dir` before the command, `--compatible` or `--best` for video commands, and `--keep-video` or `--delete-video` for `audio`. The MP3 command always uses a compatible intermediate video for conversion.

## All CLI commands

Replace `URL` with a YouTube video link, `PLAYLIST_URL` with a playlist link, and `WORDS` with search terms. Commands below run from the repository folder.

| Command | What it does |
| --- | --- |
| `uv run yt-downloader download "URL"` | Download a video with audio using the saved quality setting |
| `uv run yt-downloader download "URL" -o "my-video.mp4"` | Choose an output name; the extension follows the actual container |
| `uv run yt-downloader download "URL" --compatible` | Prefer an H.264/AAC MP4 |
| `uv run yt-downloader download "URL" --best` | Use the highest quality for this run |
| `uv run yt-downloader download "URL" --max-height 1080` | Pick the best format up to 1080p |
| `uv run yt-downloader playlist "PLAYLIST_URL"` | Download the whole playlist into its own named folder |
| `uv run yt-downloader playlist "PLAYLIST_URL" --compatible` | Download the playlist as compatible MP4 files |
| `uv run yt-downloader playlist "PLAYLIST_URL" --best` | Use the highest quality for this playlist |
| `uv run yt-downloader playlist "PLAYLIST_URL" --first 3` | Download only the first three entries |
| `uv run yt-downloader playlist "PLAYLIST_URL" --max-height 1080` | Cap each video's height at 1080p |
| `uv run yt-downloader audio "URL"` | Download and convert to MP3; remove the temporary video |
| `uv run yt-downloader audio "URL" --keep-video` | Also keep the video used for conversion |
| `uv run yt-downloader audio "URL" --delete-video` | Delete the source video even when the saved default keeps it |
| `uv run yt-downloader info "URL"` | Show title, channel, duration, views, and URL |
| `uv run yt-downloader search WORDS` | Search YouTube; show five results |
| `uv run yt-downloader search WORDS -n 10` | Show ten search results |
| `uv run yt-downloader grab WORDS -i 2` | Download search result number two |
| `uv run yt-downloader grab WORDS -i 2 --compatible` | Download that result as a compatible MP4 |
| `uv run yt-downloader grab WORDS -i 2 --best` | Download that result at highest available quality |
| `uv run yt-downloader grab WORDS -i 2 --max-height 720` | Cap the selected video's height at 720p |
| `uv run yt-downloader batch "URL1" "URL2"` | Download several videos |
| `uv run yt-downloader batch "URL1" "URL2" --compatible` | Batch download compatible MP4 files |
| `uv run yt-downloader batch "URL1" "URL2" --best` | Batch download at highest available quality |
| `uv run yt-downloader batch "URL1" "URL2" --max-height 1080` | Cap each batch video's height at 1080p |
| `uv run yt-downloader list` | List downloaded video and audio files |
| `uv run yt-downloader storage` | Show disk space used by downloads |
| `uv run yt-downloader open` | Open the downloads folder |
| `uv run yt-downloader clear` | Delete downloads after confirmation |
| `uv run yt-downloader clear --videos-only` | Delete only videos |
| `uv run yt-downloader clear --audio-only` | Delete only audio files |
| `uv run yt-downloader clear -f` | Delete without a confirmation prompt |
| `uv run yt-downloader config show` | Show saved or built-in defaults |
| `uv run yt-downloader config path` | Show the JSON config file location |
| `uv run yt-downloader config set download-dir "PATH"` | Save the default download folder |
| `uv run yt-downloader config set quality best` | Save `best` quality (or use `compatible`) |
| `uv run yt-downloader config set keep-video true` | Keep videos after MP3 conversion by default |
| `uv run yt-downloader config reset` | Remove saved settings and restore built-in defaults |

## Options reference

| Option | Used with | Explanation | Built-in behavior |
| --- | --- | --- | --- |
| `--dir PATH` | Before commands that use downloads | Use another download folder for this run; overrides `config set download-dir` | `downloads` when no folder is saved |
| `-o NAME`, `--output NAME` | `download` | Set the video's filename; the final extension follows the output container | Video title |
| `--compatible` | `download`, `playlist`, `grab`, `batch` | Prefer H.264 video plus AAC audio in MP4; may select a lower resolution | Follows saved `quality` |
| `--best` | `download`, `playlist`, `grab`, `batch` | Choose the highest available resolution and frame rate for this run | Follows saved `quality` |
| `--max-height PIXELS` | `download`, `playlist`, `grab`, `batch` | Limit video height to a positive number, such as `1080`; combines with either quality mode | No height limit |
| `--first COUNT` | `playlist` | Process the first positive number of playlist entries | Entire playlist |
| `--keep-video` | `audio` | Keep the downloaded video after MP3 conversion | Follows saved `keep-video` |
| `--delete-video` | `audio` | Remove the downloaded video after MP3 conversion | Follows saved `keep-video` |
| `-n N`, `--limit N` | `search` | Show up to N search results | `5` |
| `-i N`, `--index N` | `grab` | Download the Nth search result, counting from 1 | `1` |
| `--videos-only` | `clear` | Delete only downloaded video files, including playlist videos | Delete videos and MP3s |
| `--audio-only` | `clear` | Delete only downloaded MP3 files | Delete videos and MP3s |
| `-f`, `--force` | `clear` | Skip the deletion confirmation prompt | Ask before deleting |
| `-h`, `--help` | Any command | Show usage and available arguments | — |

`--compatible` and `--best` are alternatives; pick one per command. `--max-height` and `--first` accept positive whole numbers. Commands such as `info`, `list`, `storage`, and `open` do not have additional command-specific options.

Use `--dir` **before** a command to choose another download folder for one run:

```powershell
uv run yt-downloader --dir "C:\Videos" download "URL"
```

Use `uv run yt-downloader --help` or `uv run yt-downloader download --help` for built-in help. By default, videos go in `downloads/` and MP3 files go in `downloads/mp3/`.

## Run `yt-downloader` from anywhere

Yes, you can add this CLI to your user `PATH`. From the repository folder, install its command with uv:

```powershell
uv tool install .
uv tool update-shell
```

Open a new terminal, then run `yt-downloader --help` or `yt-downloader download "URL"` from any directory. `uv tool update-shell` adds uv's tool executable directory to your user `PATH`. FFmpeg and Node.js or Deno still need to be available on `PATH`. To pick up later project changes, reinstall with `uv tool install --force .`.

## Updating

If YouTube changes and downloads stop working, update the extractor and sync the environment:

```powershell
uv lock --upgrade-package yt-dlp
uv sync
```

## License

[MIT](LICENSE)
