from __future__ import annotations

import statistics
from pathlib import Path


def analyze_video(source: Path, duration_ms: int, sample_fps: float = .5) -> dict:
    """Extract a compact visual timeline in one low-resolution pass.

    This deliberately avoids a heavyweight detector. The signals are stable and
    useful for editorial ranking while keeping local CPU usage bounded: scene
    changes come from frame difference, faces from the bundled Haar cascade, and
    moving regions provide a generic object/activity cue.
    """
    try:
        import cv2
    except ImportError:
        return {"samples": [], "scene_cuts": []}
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        return {"samples": [], "scene_cuts": []}
    interval_ms = max(1000, round(1000 / max(sample_fps, .1)))
    source_fps = max(1.0, float(capture.get(cv2.CAP_PROP_FPS) or 30.0))
    frame_interval = max(1, round(source_fps / max(sample_fps, .1)))
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    samples: list[dict] = []
    scene_cuts: list[float] = []
    previous_gray = None
    try:
        frame_index = 0
        next_sample = 0
        while next_sample < duration_ms:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index < next_sample / 1000 * source_fps:
                frame_index += 1
                continue
            position = round(frame_index / source_fps * 1000)
            height, width = frame.shape[:2]
            scale = min(1.0, 480 / max(width, 1))
            scan = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            gray = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY)
            motion = .0
            if previous_gray is not None:
                delta = cv2.absdiff(previous_gray, gray)
                motion = min(1.0, float(delta.mean()) / 42.0)
                if motion >= .42:
                    scene_cuts.append(position / 1000)
            previous_gray = gray
            faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(24, 24))
            face_items = []
            for x, y, face_width, face_height in sorted(faces, key=lambda box: box[2] * box[3], reverse=True)[:4]:
                face_items.append({
                    "x": round((x + face_width / 2) / max(scan.shape[1], 1), 4),
                    "y": round((y + face_height / 2) / max(scan.shape[0], 1), 4),
                    "size": round(min(1.0, (face_width * face_height) / max(scan.shape[0] * scan.shape[1], 1) * 8), 4),
                })
            samples.append({
                "time": position / 1000,
                "motion": round(motion, 4),
                "object_activity": round(min(1.0, motion * 1.35), 4),
                "faces": face_items,
                "speaker": 0 if face_items and face_items[0]["size"] >= .08 else None,
            })
            frame_index += 1
            next_sample = position + interval_ms
    finally:
        capture.release()
    return {"samples": samples, "scene_cuts": _dedupe_times(scene_cuts)}


def enrich_transcript(transcript: list[dict], visual: dict) -> list[dict]:
    samples = visual.get("samples", [])
    cuts = visual.get("scene_cuts", [])
    if not samples:
        return transcript
    for segment in transcript:
        start, end = float(segment["start"]), float(segment["end"])
        relevant = [item for item in samples if start <= float(item["time"]) <= end]
        if not relevant:
            relevant = [min(samples, key=lambda item: abs(float(item["time"]) - (start + end) / 2))]
        motion = statistics.fmean(float(item.get("motion", 0)) for item in relevant)
        object_activity = statistics.fmean(float(item.get("object_activity", 0)) for item in relevant)
        face_samples = [item for item in relevant if item.get("faces")]
        segment["visual_motion"] = round(motion, 4)
        segment["visual_activity"] = round(object_activity, 4)
        segment["face_presence"] = round(len(face_samples) / len(relevant), 4)
        segment["speaker_confidence"] = round(min(1.0, len(face_samples) / max(1, len(relevant)) * 1.15), 4)
        segment["scene_change"] = round(sum(start <= cut <= end for cut in cuts) / max(1, len(relevant)), 4)
    return transcript


def _dedupe_times(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] >= 1.0:
            result.append(round(value, 3))
    return result
