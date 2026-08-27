"""Run the real ASR -> curation -> captions -> render path on one local video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nixclip_processor.media import render_clip, write_srt
from nixclip_processor.models import Preferences, ProjectJob
from nixclip_processor.pipeline import pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    preferences = Preferences(language="pt", clip_length="short", clip_count=1, captions=True)
    transcript = pipeline._transcribe(args.source, preferences.language)
    job = ProjectJob(id="verification", title="Verificação", preferences=preferences)
    clips = pipeline._curate(transcript, job)
    if not clips:
        raise RuntimeError("A amostra não gerou candidatos.")

    clip = clips[0]
    subtitle = args.output_dir / "verification.srt"
    output = args.output_dir / "verification.mp4"
    write_srt(subtitle, transcript, clip.start_ms, clip.end_ms)
    clip.reframe_mode = render_clip(args.source, output, clip.start_ms, clip.end_ms, preferences, subtitle)
    print(json.dumps({"transcriptSegments": len(transcript), "clip": clip.model_dump(by_alias=True), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
