from __future__ import annotations

import json
import statistics
import subprocess
from urllib.parse import urlparse
from urllib.request import urlopen
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
    preferences: Preferences, subtitle_path: Path | None = None, logo_path: Path | None = None,
) -> str:
    source_width, source_height = source_dimensions(source)
    # Do not spend CPU and bitrate manufacturing pixels that do not exist in a
    # 720p source. Full-HD inputs still render at the original 1080 target.
    width, height = target_dimensions(source_width, source_height, preferences.aspect_ratio)
    template = preferences.brand_template
    template_layout = str(template.get("layout", "fill"))
    if preferences.auto_reframe and template_layout != "fit":
        trajectory = detect_focus_trajectory(source, start_ms, end_ms)
        focus_x = statistics.median([point[1] for point in trajectory]) if trajectory else .5
        focus_y = statistics.median([point[2] for point in trajectory]) if trajectory else .45
        detected = bool(trajectory)
        crop_width, crop_height, crop_x, crop_y = crop_geometry(
            source_width, source_height, width / height, focus_x, focus_y,
        )
        if trajectory:
            x_points = [(time, focus * source_width - crop_width / 2) for time, focus, _ in trajectory]
            y_points = [(time, focus * source_height - crop_height / 2) for time, _, focus in trajectory]
            x_filter = piecewise_focus_expression(x_points, source_width - crop_width)
            y_filter = piecewise_focus_expression(y_points, source_height - crop_height)
        else:
            x_filter, y_filter = str(crop_x), str(crop_y)
        filters = [f"crop={crop_width}:{crop_height}:{x_filter}:{y_filter}", f"scale={width}:{height}"]
        reframe_mode = "face-aware" if detected else "center"
    else:
        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        ]
        reframe_mode = "fit"
    if preferences.captions and subtitle_path:
        escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        preset = str(template.get("captionPreset", "Nix Pop"))
        preset_style = {
            "Impacto": ("&H0000FFFF", "&H00000000", 4, 2),
            "Minimal": ("&H00FFFFFF", "&H00000000", 1, 0),
            "Karaokê": ("&H0000FFFF", "&H00000000", 3, 1),
        }.get(preset, ("&H00FFFFFF", "&H00000000", 3, 1))
        font = str(template.get("font", "Arial")).replace(",", "")
        size = max(12, min(72, int(template.get("fontSize", 40))))
        position = {"top": 8, "middle": 5, "bottom": 2}.get(str(template.get("captionPosition", "bottom")), 2)
        primary = ass_color(str(template.get("captionColor", "")), preset_style[0])
        outline_color = ass_color(str(template.get("outlineColor", "")), preset_style[1])
        outline = max(0, min(12, int(template.get("captionOutline", preset_style[2]))))
        shadow = max(0, min(12, int(template.get("captionShadow", preset_style[3]))))
        style = f"FontName={font},FontSize={size},Bold=1,PrimaryColour={primary},OutlineColour={outline_color},BorderStyle=1,Outline={outline},Shadow={shadow},Alignment={position},MarginV=110"
        filters.append(f"subtitles=filename='{escaped}':force_style='{style}'")
    title = str(template.get("brandTitle", "")).strip()
    if title:
        filters.append(drawtext_filter(title, y="h*0.07", fontsize=32, box_color="0x0b0914@0.72"))
    cta = str(template.get("ctaText", "")).strip()
    if cta:
        filters.append(drawtext_filter(cta, y="h*0.82", fontsize=20, box_color="0x7c2cff@0.86"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [settings.ffmpeg, "-y", "-ss", f"{start_ms / 1000:.3f}", "-i", str(source)]
    if logo_path and logo_path.exists():
        logo_size = max(64, round(width * .16))
        base = ",".join(filters)
        command += ["-loop", "1", "-i", str(logo_path), "-filter_complex", f"[0:v]{base}[base];[1:v]scale={logo_size}:-1[logo];[base][logo]overlay=W-w-28:28[outv]", "-map", "[outv]", "-map", "0:a?", "-shortest"]
    else:
        command += ["-vf", ",".join(filters)]
    command += ["-t", f"{(end_ms - start_ms) / 1000:.3f}", "-c:v", "libx264", "-preset", "superfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destination)]
    subprocess.run(command, check=True, capture_output=True)
    return reframe_mode


def target_dimensions(source_width: int, source_height: int, aspect_ratio: str) -> tuple[int, int]:
    high_resolution = min(source_width, source_height) > 720
    dimensions = (
        {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}
        if high_resolution else
        {"9:16": (720, 1280), "1:1": (720, 720), "16:9": (1280, 720), "4:5": (720, 900)}
    )
    return dimensions[aspect_ratio]


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


def piecewise_focus_expression(points: list[tuple[float, float]], maximum: int) -> str:
    """Build a bounded, linearly interpolated FFmpeg expression from focus keyframes."""
    if not points:
        return "0"
    bounded = [(max(0.0, time), max(0.0, min(float(maximum), value))) for time, value in points]
    if len(bounded) == 1:
        return str(round(bounded[0][1]))
    expression = str(round(bounded[-1][1]))
    for index in range(len(bounded) - 2, -1, -1):
        time, value = bounded[index]
        next_time, next_value = bounded[index + 1]
        delta = max(.001, next_time - time)
        slope = (next_value - value) / delta
        interpolated = f"{value:.3f}+({slope:.3f})*(t-{time:.3f})"
        expression = f"if(lt(t\\,{next_time:.3f})\\,{interpolated}\\,{expression})"
    return f"max(0\\,min({maximum}\\,{expression}))"


def detect_focus_trajectory(source: Path, start_ms: int, end_ms: int) -> list[tuple[float, float, float]]:
    try:
        import cv2
    except ImportError:
        return []
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        return []
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    duration = max(1, end_ms - start_ms)
    sample_count = min(48, max(12, duration // 850))
    points: list[tuple[float, float, float]] = []
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
            center_x = sum(x + face_width / 2 for x, _, face_width, _ in weighted) / len(weighted) / scan.shape[1]
            center_y = sum(y + face_height / 2 for _, y, _, face_height in weighted) / len(weighted) / scan.shape[0]
            time = (position - start_ms) / 1000
            points.append((time, center_x, center_y))
    finally:
        capture.release()
    if not points:
        return []
    smoothed: list[tuple[float, float, float]] = [points[0]]
    for time, center_x, center_y in points[1:]:
        _, previous_x, previous_y = smoothed[-1]
        smoothed.append((time, previous_x * .68 + center_x * .32, previous_y * .68 + center_y * .32))
    return smoothed


def detect_visual_focus(source: Path, start_ms: int, end_ms: int) -> tuple[float, float, bool]:
    trajectory = detect_focus_trajectory(source, start_ms, end_ms)
    if not trajectory:
        return .5, .45, False
    return statistics.median([point[1] for point in trajectory]), statistics.median([point[2] for point in trajectory]), True


def write_srt(path: Path, transcript: list[dict], clip_start_ms: int, clip_end_ms: int, uppercase: bool = False) -> None:
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
        entries.append(f"{len(entries) + 1}\n{timestamp(start - clip_start_ms)} --> {timestamp(end - clip_start_ms)}\n{text.upper() if uppercase else text}\n")
    path.write_text("\n".join(entries), encoding="utf-8")


def timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(max(milliseconds, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def ass_color(value: str, fallback: str) -> str:
    if len(value) != 7 or not value.startswith("#"):
        return fallback
    try:
        red, green, blue = value[1:3], value[3:5], value[5:7]
        int(red + green + blue, 16)
        return f"&H00{blue}{green}{red}".upper()
    except ValueError:
        return fallback


def drawtext_filter(text: str, y: str, fontsize: int, box_color: str) -> str:
    safe = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    return f"drawtext=text='{safe}':fontcolor=white:fontsize={fontsize}:x=(w-text_w)/2:y={y}:box=1:boxcolor={box_color}:boxborderw=12"


def download_brand_logo(preferences: Preferences, destination: Path) -> Path | None:
    url = preferences.brand_template.get("brandLogoUrl")
    if not isinstance(url, str) or urlparse(url).scheme != "https":
        return None
    try:
        with urlopen(url, timeout=15) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"image/png", "image/jpeg", "image/webp"}:
                return None
            data = response.read(5 * 1024 * 1024 + 1)
        if not data or len(data) > 5 * 1024 * 1024:
            return None
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[content_type]
        target = destination / f"brand-logo{suffix}"
        target.write_bytes(data)
        return target
    except Exception:
        return None
