from __future__ import annotations

from pathlib import Path

from .config import settings


def detect_objects(source: Path, duration_ms: int, sample_fps: float = .5) -> dict:
    """Run optional YOLO tracking, with a deterministic empty fallback.

    Ultralytics is intentionally lazy-loaded: a private CPU install does not
    pay the dependency/model cost unless advanced vision is enabled.
    """
    try:
        from ultralytics import YOLO
    except (ImportError, ModuleNotFoundError):
        return {"backend": "fallback", "tracks": []}
    model_name = settings.yolo_model
    try:
        import cv2

        model = YOLO(model_name)
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            return {"backend": "fallback", "tracks": [], "error": "video unavailable"}
        tracks: list[dict] = []
        interval_ms = max(500, round(1000 / max(sample_fps, .1)))
        try:
            for position_ms in range(0, max(0, duration_ms), interval_ms):
                capture.set(cv2.CAP_PROP_POS_MSEC, position_ms)
                ok, image = capture.read()
                if not ok:
                    break
                results = model.track(source=image, persist=True, verbose=False, conf=.35)
                frame = results[0] if results else None
                boxes = getattr(frame, "boxes", None)
                if boxes is None:
                    continue
                names = getattr(frame, "names", {})
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    cls = int(box.cls[0]) if box.cls is not None else -1
                    track_id = int(box.id[0]) if box.id is not None else None
                    tracks.append({
                        "time": round(position_ms / 1000, 3), "id": track_id,
                        "class": names.get(cls, str(cls)),
                        "confidence": round(float(box.conf[0]), 4),
                        "center_x": round(((xyxy[0] + xyxy[2]) / 2) / max(frame.orig_shape[1], 1), 4),
                        "center_y": round(((xyxy[1] + xyxy[3]) / 2) / max(frame.orig_shape[0], 1), 4),
                        "area": round((xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]) / max(frame.orig_shape[0] * frame.orig_shape[1], 1), 5),
                    })
        finally:
            capture.release()
        return {"backend": "yolo-track", "tracks": tracks}
    except Exception as error:  # optional accelerator/model failure must not stop a job
        return {"backend": "fallback", "tracks": [], "error": str(error)}


def diarize(audio_path: Path) -> dict:
    """Run optional pyannote speaker diarization when a HF token is configured."""
    token = settings.hf_token.strip()
    if not token:
        return {"backend": "unavailable", "segments": []}
    try:
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
        diarization = pipeline(str(audio_path))
        segments = [
            {"start": round(turn.start, 3), "end": round(turn.end, 3), "speaker": str(label)}
            for turn, _, label in diarization.itertracks(yield_label=True)
        ]
        return {"backend": "pyannote", "segments": segments}
    except Exception as error:  # credentials/model/runtime are optional
        return {"backend": "unavailable", "segments": [], "error": str(error)}


def enrich_with_advanced_signals(transcript: list[dict], objects: dict, speakers: dict) -> list[dict]:
    tracks = objects.get("tracks", [])
    speaker_segments = speakers.get("segments", [])
    for segment in transcript:
        start, end = float(segment["start"]), float(segment["end"])
        visible = [track for track in tracks if start <= float(track["time"]) <= end]
        segment["tracked_objects"] = len({track.get("id") for track in visible if track.get("id") is not None})
        segment["object_confidence"] = round(sum(float(track.get("confidence", 0)) for track in visible) / len(visible), 4) if visible else 0
        matching_speakers = [item["speaker"] for item in speaker_segments if float(item["start"]) < end and float(item["end"]) > start]
        if matching_speakers:
            segment["speaker"] = max(set(matching_speakers), key=matching_speakers.count)
            segment["speaker_confidence"] = round(len(matching_speakers) / max(1, len(speaker_segments)), 4)
    return transcript
