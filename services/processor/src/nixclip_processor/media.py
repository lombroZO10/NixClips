from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import settings
from .models import MediaSummary, Preferences


def probe_media(source: Path) -> MediaSummary:
    process = subprocess.run(
        [settings.ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    payload = json.loads(process.stdout)
    video = next((stream for stream in payload["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in payload["streams"] if stream.get("codec_type") == "audio"), None)
    if not video:
        raise ValueError("O arquivo não contém uma faixa de vídeo válida.")
    numerator, denominator = (video.get("avg_frame_rate") or "0/1").split("/")
    fps = float(numerator) / max(float(denominator), 1)
    duration = float(video.get("duration") or payload.get("format", {}).get("duration") or 0)
    return MediaSummary(
        duration_ms=round(duration * 1000), width=int(video["width"]), height=int(video["height"]),
        fps=round(fps, 3), video_codec=video.get("codec_name", "unknown"),
        audio_codec=audio.get("codec_name") if audio else None,
    )


def render_clip(
    source: Path, destination: Path, start_ms: int, end_ms: int,
    preferences: Preferences, subtitle_path: Path | None = None,
) -> None:
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    width, height = dimensions[preferences.aspect_ratio]
    filters = [f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}"]
    if preferences.captions and subtitle_path:
        escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        style = "FontName=Arial,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=145"
        filters.append(f"subtitles=filename='{escaped}':force_style='{style}'")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.ffmpeg, "-y", "-ss", f"{start_ms / 1000:.3f}", "-i", str(source),
        "-t", f"{(end_ms - start_ms) / 1000:.3f}", "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True)


def write_srt(path: Path, transcript: list[dict], clip_start_ms: int, clip_end_ms: int) -> None:
    captions: list[tuple[int, int, str]] = []
    for segment in transcript:
        words = [word for word in segment.get("words", []) if word.get("start") is not None and word.get("end") is not None]
        if words:
            for offset in range(0, len(words), 5):
                group = words[offset:offset + 5]
                captions.append((int(group[0]["start"] * 1000), int(group[-1]["end"] * 1000), "".join(word["text"] for word in group).strip()))
        else:
            captions.append((int(segment["start"] * 1000), int(segment["end"] * 1000), segment["text"].strip()))
    entries: list[str] = []
    for start, end, text in captions:
        start, end = max(start, clip_start_ms), min(end, clip_end_ms)
        if end <= start or not text:
            continue
        entries.append(f"{len(entries) + 1}\n{timestamp(start - clip_start_ms)} --> {timestamp(end - clip_start_ms)}\n{text}\n")
    path.write_text("\n".join(entries), encoding="utf-8")


def timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(max(milliseconds, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
