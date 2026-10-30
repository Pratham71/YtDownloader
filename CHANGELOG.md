# Changelog

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
