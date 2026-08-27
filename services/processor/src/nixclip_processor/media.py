from __future__ import annotations

import json
import statistics
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
) -> str:
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    width, height = dimensions[preferences.aspect_ratio]
    if preferences.auto_reframe:
        focus_x, focus_y, detected = detect_visual_focus(source, start_ms, end_ms)
        source_width, source_height = source_dimensions(source)
        crop_width, crop_height, crop_x, crop_y = crop_geometry(
            source_width, source_height, width / height, focus_x, focus_y,
        )
        filters = [f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}", f"scale={width}:{height}"]
        reframe_mode = "face-aware" if detected else "center"
    else:
        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        ]
        reframe_mode = "fit"
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
    return reframe_mode


def source_dimensions(source: Path) -> tuple[int, int]:
    media = probe_media(source)
    return media.width, media.height


def crop_geometry(
    source_width: int, source_height: int, target_ratio: float,
    focus_x: float = .5, focus_y: float = .5,
) -> tuple[int, int, int, int]:
    source_ratio = source_width / max(source_height, 1)
    if source_ratio > target_ratio:
        crop_height = source_height - source_height % 2
        crop_width = min(source_width, int(crop_height * target_ratio))
        crop_width -= crop_width % 2
        x = round(focus_x * source_width - crop_width / 2)
        return crop_width, crop_height, max(0, min(x, source_width - crop_width)), 0
    crop_width = source_width - source_width % 2
    crop_height = min(source_height, int(crop_width / target_ratio))
    crop_height -= crop_height % 2
    y = round(focus_y * source_height - crop_height / 2)
    return crop_width, crop_height, 0, max(0, min(y, source_height - crop_height))


def detect_visual_focus(source: Path, start_ms: int, end_ms: int) -> tuple[float, float, bool]:
    try:
        import cv2
    except ImportError:
        return .5, .45, False
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        return .5, .45, False
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    duration = max(1, end_ms - start_ms)
    sample_count = min(48, max(12, duration // 850))
    centers_x: list[float] = []
    centers_y: list[float] = []
    try:
        for index in range(sample_count):
            position = start_ms + duration * (index + .5) / sample_count
            capture.set(cv2.CAP_PROP_POS_MSEC, position)
            ok, frame = capture.read()
            if not ok:
                continue
            frame_width = frame.shape[1]
            scale = min(1.0, 720 / max(frame_width, 1))
            scan = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            gray = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(32, 32))
            if len(faces) == 0:
                continue
            weighted = sorted(faces, key=lambda box: box[2] * box[3], reverse=True)[:3]
            centers_x.append(sum(x + face_width / 2 for x, _, face_width, _ in weighted) / len(weighted) / scan.shape[1])
            centers_y.append(sum(y + face_height / 2 for _, y, _, face_height in weighted) / len(weighted) / scan.shape[0])
    finally:
        capture.release()
    if not centers_x:
        return .5, .45, False
    return statistics.median(centers_x), statistics.median(centers_y), True


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
