# Changelog

## 0.3.0

### Added

- Downloads from TikTok, Instagram, X, Reddit, Vimeo, SoundCloud, and the other sites yt-dlp supports, not only YouTube. `ytdl sites [FILTER]` lists them.
- Multi-video posts, such as Instagram carousels, save every video.
- `--cookies-from-browser BROWSER[:PROFILE]` and `--cookies FILE` for sites that need a login, plus the `cookies-from-browser` setting. Login errors suggest them.
- Title, channel, date, chapters, and thumbnail are embedded into videos and MP3s by default. Turn off with `--no-metadata` or the `embed-metadata` setting.
- `--subs [LANGS]` embeds subtitles, falling back to auto-generated ones.
- `ytdl formats URL` lists every format; `download -f ID` downloads one and `download --choose` asks which.
- `batch` and `playlist` download in parallel with `-j N` (up to 8) and the `jobs` setting.
- `batch` and `playlist` remember finished videos per folder and skip them on the next run; `--force` downloads again.
- `batch --file FILE` reads URLs from a text file.
- Search results are cached for an hour, so `grab` downloads the result `search` showed.
- Ctrl+C stops every running download in a batch or playlist.

### Changed

- Default filenames are `Title [id].ext`, so videos with the same title no longer overwrite each other. Playlist files are `001 - Title [id].ext`. With `-o NAME`, a multi-video post is saved as `NAME - 1.ext`, `NAME - 2.ext`, and so on.
- `--max-height` and `--compatible` work on sites that do not report a video height or that name H.264 `h264`, such as Instagram and TikTok.
- Playlist downloads show one progress bar per video and a summary of downloaded, skipped, and failed videos.
- Audio files saved directly by audio-only sites (`.m4a`, `.opus`, and others) appear in `list`, `storage`, and `clear`.
- yt-dlp is now at least 2026.10.26 and includes `curl_cffi`, which some sites require.

### Fixed

- Errors were printed twice, and site names such as `[vimeo]` disappeared from messages.
- Titles and filenames containing square brackets were shown incorrectly in tables.

## 0.2.0

### Changed

- Renamed the project, package, and command from `yt-downloader` to `ytdl`. Settings in the old `yt-downloader` config folder are moved automatically.
- The default download folder is now `~/Downloads/ytdl` instead of a `downloads` folder in the current directory.
- On macOS, settings are stored in `~/Library/Application Support/ytdl/`.
- `YTDL_CONFIG_FILE` replaces `YT_DOWNLOADER_CONFIG_FILE`; the old name still works.
- `ytdl audio` downloads only the audio stream when the video is not kept, which is faster and smaller.
- MP3 conversion uses FFmpeg directly. `moviepy` and `youtube-search-python` are no longer dependencies.

### Added

- `ytdl update` upgrades ytdl and yt-dlp for uv, pipx, pip, and git-checkout installs, with `--check` and `--dry-run`.
- A daily background update check that prints a notice when ytdl or yt-dlp has a newer version. Turn it off with `ytdl config set check-updates false` or `YTDL_NO_UPDATE_CHECK=1`.
- `ytdl doctor` checks FFmpeg, ffprobe, and the JavaScript runtime, with install commands for Windows, macOS, and Linux.
- `ytdl --version`.
- One-line installers: `scripts/install.ps1` for Windows and `scripts/install.sh` for macOS and Linux.

### Fixed

- `ytdl search` and `ytdl grab` failed with `post() got an unexpected keyword argument 'proxies'`. Search now uses yt-dlp.
- `ytdl open` no longer passes the folder path through a shell on macOS and Linux.
- `search -n` and `grab -i` reject zero and negative numbers.

## 0.1.0

- First release as `yt-downloader`: video, playlist, MP3, search, batch, and saved defaults.
