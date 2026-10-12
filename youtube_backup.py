#!/usr/bin/env python3
"""
YouTube Backup Tool
Downloads a YouTube channel or playlist as MP4 files with clean filenames
(YYYYMMDD - Title.mp4), extracts metadata, supports resume via download archive,
and writes a JSON manifest. Optional cloud upload step (stub for rclone).

Usage:
    python youtube_backup.py <URL> [-o OUTPUT_DIR] [--upload]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.logging import RichHandler

console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
log = logging.getLogger("ytbackup")


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in Windows filenames."""
    # Windows invalid: < > : " / \ | ? *
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Limit length
    if len(name) > 180:
        name = name[:180].rstrip()
    return name or "untitled"


def extract_metadata(info: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the fields we care about from a yt-dlp info dict."""
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "upload_date": info.get("upload_date"),  # YYYYMMDD
        "description": info.get("description"),
        "tags": info.get("tags") or [],
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "channel": info.get("channel"),
        "url": info.get("webpage_url") or info.get("url"),
        "view_count": info.get("view_count"),
    }


def list_videos(url: str) -> List[Dict[str, Any]]:
    """Extract flat playlist/channel info without downloading."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = info.get("entries") or []
    # Filter out None entries (errors)
    return [e for e in entries if e and e.get("id")]


def download_and_collect(
    url: str,
    output_dir: Path,
    archive_path: Path,
) -> List[Dict[str, Any]]:
    """
    Download videos, skipping those in the archive.
    Returns list of metadata dicts for successfully processed videos.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Custom filename template: YYYYMMDD - Title.mp4
    # yt-dlp will merge to mp4 when possible
    outtmpl = str(output_dir / "%(upload_date)s - %(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "download_archive": str(archive_path),
        "ignoreerrors": True,
        "noplaylist": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "quiet": False,
        "no_warnings": False,
        "progress_hooks": [progress_hook],
        "restrictfilenames": False,  # we sanitize ourselves if needed
    }

    collected: List[Dict[str, Any]] = []

    def postprocessor_hook(d: Dict[str, Any]) -> None:
        if d["status"] == "finished":
            info = d.get("info_dict", {})
            meta = extract_metadata(info)
            if meta["id"]:
                collected.append(meta)

    # Attach hook via progress for finished status
    # yt-dlp progress_hooks also get finished events
    def progress_hook(d: Dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            # Keep quiet; rich handles display if we want, but yt-dlp is fine
            pass
        elif status == "finished":
            info = d.get("info_dict", {})
            meta = extract_metadata(info)
            if meta.get("id") and meta not in collected:
                collected.append(meta)
                title = meta.get("title") or meta["id"]
                console.print(f"[green]✓[/green] Finished: {title}")

    ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            log.error(f"Download failed: {e}")

    return collected


def write_manifest(output_dir: Path, metadata: List[Dict[str, Any]]) -> Path:
    """Write a JSON manifest next to the videos."""
    manifest_path = output_dir / "manifest.json"
    # Load existing if present and merge by id
    existing: Dict[str, Dict[str, Any]] = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    if item.get("id"):
                        existing[item["id"]] = item
        except Exception:
            pass

    for item in metadata:
        if item.get("id"):
            existing[item["id"]] = item

    sorted_items = sorted(existing.values(), key=lambda x: x.get("upload_date") or "", reverse=True)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(sorted_items, f, indent=2, ensure_ascii=False)

    console.print(f"[cyan]Manifest written:[/cyan] {manifest_path} ({len(sorted_items)} entries)")
    return manifest_path


def optional_upload(output_dir: Path) -> None:
    """
    Stub for cloud upload.
    Example: rclone sync output_dir remote:youtube-backup
    Uncomment and configure as needed.
    """
    console.print("[yellow]Upload step not implemented.[/yellow] Configure rclone or Google Drive API here.")
    # Example:
    # import subprocess
    # subprocess.run(["rclone", "sync", str(output_dir), "gdrive:youtube-backup", "--progress"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup a YouTube channel or playlist to local MP4 files with metadata."
    )
    parser.add_argument("url", help="YouTube channel or playlist URL")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("./downloads"),
        help="Output directory (default: ./downloads)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List videos without downloading",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Run optional cloud upload step after download",
    )
    args = parser.parse_args()

    console.print(f"[bold]YouTube Backup[/bold] → {args.output.resolve()}")

    if args.list_only:
        console.print("Listing videos...")
        entries = list_videos(args.url)
        console.print(f"Found {len(entries)} videos:")
        for i, e in enumerate(entries, 1):
            title = e.get("title") or e.get("id")
            console.print(f"  {i:3d}. {title}")
        return

    archive = args.output / "archive.txt"
    console.print(f"Using download archive: {archive}")

    metadata = download_and_collect(args.url, args.output, archive)
    write_manifest(args.output, metadata)

    if args.upload:
        optional_upload(args.output)

    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(1)
