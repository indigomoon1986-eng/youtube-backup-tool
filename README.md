# youtube-backup-tool

Lightweight YouTube channel/playlist backup tool.

Takes a YouTube channel or playlist URL and downloads every video as an MP4 with clean filenames that include the upload date and title (`YYYYMMDD - Title.mp4`), plus a JSON metadata manifest with descriptions and tags.

Runs locally on Windows (or anywhere Python runs). Optional cloud upload step.

## Features

- Resume support via download archive (`archive.txt`) — skips already-downloaded videos
- Clean filenames: `YYYYMMDD - Title.mp4`
- JSON manifest (`manifest.json`) with title, date, description, tags, duration, etc.
- Simple command-line interface
- Progress output via yt-dlp + rich
- Optional upload stub (rclone / Google Drive)

## Quick Start

```bash
# Install
pip install -r requirements.txt

# List videos without downloading
python youtube_backup.py "https://www.youtube.com/playlist?list=..." --list-only

# Download everything
python youtube_backup.py "https://www.youtube.com/@channel" -o ./my-backup

# Download + optional upload step
python youtube_backup.py "URL" -o ./backup --upload
```

## Requirements

- Python 3.9+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed via requirements)
- ffmpeg on PATH (recommended for best MP4 merging)

## Architecture

| Module              | Responsibility                                      |
|---------------------|-----------------------------------------------------|
| Input handler       | URL + output path (argparse)                        |
| Downloader          | Wraps `yt_dlp.YoutubeDL` with archive + format opts |
| Metadata extractor  | Pulls title, upload_date, description, tags         |
| Progress logger     | Status without flooding the screen (rich)           |
| Optional uploader   | Stub for rclone / Google Drive                     |

### Data flow

1. User pastes URL
2. Tool validates and can list videos (`--list-only`)
3. Downloads each video (skips those in `archive.txt`)
4. Writes/updates `manifest.json` next to the files
5. Optionally syncs the folder to cloud storage

## Tech Stack

- Python 3
- yt-dlp (library)
- pathlib
- rich (logging / console)
- rclone or Google Drive API for upload (optional)

## Next Steps

- Improve progress bar (per-video rich progress)
- Add basic GUI (e.g. tkinter or customtkinter)
- Full rclone / Drive uploader implementation
- CSV manifest option
- Subtitle download toggle

## License

MIT
