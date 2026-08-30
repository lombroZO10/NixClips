import sys
from pathlib import Path

from nixclip_processor.visual import analyze_video


def test_visual_analysis_degrades_when_cv2_install_is_incomplete(monkeypatch) -> None:
    class IncompleteCv2:
        VideoCapture = object

    monkeypatch.setitem(sys.modules, "cv2", IncompleteCv2())

    result = analyze_video(Path("video.mp4"), 10_000)

    assert result == {"samples": [], "scene_cuts": [], "backend": "unavailable"}
