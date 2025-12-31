"""
Utilities for pulling YouTube transcripts and metadata via yt-dlp.

Used by background missions to focus on the user's preferred channels.
"""

from __future__ import annotations

import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from yt_dlp import YoutubeDL  # type: ignore

from core import notes_manager


def _plain_text_from_vtt(vtt_text: str) -> str:
    """Strip WEBVTT cues/timestamps and return plain text."""
    lines: List[str] = []
    for raw_line in vtt_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("WEBVTT") or line.isdigit():
            continue
        if "-->" in line:
            continue
        lines.append(line)
    text = " ".join(lines)
    # Collapse repeated whitespace
    return re.sub(r"\s+", " ", text).strip()


def _extract_video_id(video_url: str) -> Optional[str]:
    if not video_url:
        return None
    if re.fullmatch(r"[A-Za-z0-9_-]{8,}", video_url.strip()):
        return video_url.strip()
    parsed = urllib.parse.urlparse(video_url)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.lstrip("/")
    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            qs = urllib.parse.parse_qs(parsed.query)
            return (qs.get("v") or [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[-1].split("/")[0]
    return None


def _fetch_transcript_api(video_url: str) -> Optional[Dict[str, str]]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception:
        return None
    video_id = _extract_video_id(video_url)
    if not video_id:
        return None
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            text = " ".join(item.get("text", "") for item in transcript if item.get("text"))
        else:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=["en"])
            text = " ".join(snippet.text for snippet in fetched if getattr(snippet, "text", ""))
    except Exception:
        return None
    if not text:
        return None
    raw_path = notes_manager.log_command_snapshot(
        ["youtube-transcript-api", video_id],
        f"youtube-api-{video_id}",
        text,
    )
    return {
        "video_id": video_id,
        "title": f"YouTube Video {video_id}",
        "url": video_url,
        "transcript": text.strip(),
        "raw_path": str(raw_path),
    }


def list_latest_videos(channel_url: str, limit: int = 3) -> List[Dict[str, str]]:
    """Return metadata for the latest videos on a channel."""
    opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": limit,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "geo_bypass": True,
    }
    videos: List[Dict[str, str]] = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    except Exception:
        return videos

    entries = info.get("entries") or []
    for entry in entries[:limit]:
        video_id = entry.get("id")
        url = entry.get("url")
        title = entry.get("title", "")
        if not url:
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                continue
        videos.append(
            {
                "id": video_id or url,
                "url": url,
                "title": title or "Untitled video",
            }
        )
    return videos


def fetch_transcript(video_url: str, label: str = "youtube") -> Optional[Dict[str, str]]:
    """
    Download an English transcript (auto subtitles if needed) for a video.

    Returns dict with transcript text, title, video id, and raw storage path,
    or None if no transcript was available.
    """
    api_result = _fetch_transcript_api(video_url)
    if api_result:
        return api_result
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp_dir.name)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "outtmpl": str(tmp_path / "%(id)s"),
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_id = info.get("id") or label
            title = info.get("title", "YouTube Video")
            ydl.download([video_url])
    except Exception:
        tmp_dir.cleanup()
        return None

    transcript_file: Optional[Path] = None
    for candidate in tmp_path.glob("*.vtt"):
        transcript_file = candidate
        break
    if not transcript_file or not transcript_file.exists():
        tmp_dir.cleanup()
        return None

    try:
        raw_text = transcript_file.read_text(encoding="utf-8")
    except Exception:
        tmp_dir.cleanup()
        return None

    plain_text = _plain_text_from_vtt(raw_text)
    if not plain_text:
        tmp_dir.cleanup()
        return None

    raw_path = notes_manager.log_command_snapshot(
        ["yt-dlp", "--write-auto-sub", "--skip-download", video_url],
        f"youtube-{label}",
        plain_text,
    )

    tmp_dir.cleanup()
    return {
        "video_id": info.get("id", label),
        "title": info.get("title", "YouTube Video"),
        "url": video_url,
        "transcript": plain_text,
        "raw_path": str(raw_path),
    }


__all__ = ["list_latest_videos", "fetch_transcript"]
