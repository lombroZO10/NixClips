from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from .config import settings
from .media import probe_media, render_clip, write_srt
from .models import ClipResult, ProjectJob, Stage
from .repository import repository
from .scoring import lexical_signals, score_candidate


class Pipeline:
    def __init__(self) -> None:
        self._asr = None
        self._asr_device = None
        self._job_lock = asyncio.Lock()

    async def run(self, project_id: str) -> None:
        async with self._job_lock:
            await self._run_serial(project_id)

    async def _run_serial(self, project_id: str) -> None:
        job = await repository.get(project_id)
        if not job:
            return
        try:
            if job.source_url and not job.source_path:
                await self._update(job, Stage.IMPORT, 4, "Baixando o vídeo original")
                job.source_path = str(await asyncio.to_thread(self._download, job))

            source = Path(job.source_path or "")
            await self._update(job, Stage.IMPORT, 10, "Inspecionando faixas, duração e resolução")
            job.media = await asyncio.to_thread(probe_media, source)
            await repository.save(job)

            await self._update(job, Stage.ANALYZE, 22, "Transcrevendo e alinhando a fala")
            transcript = await asyncio.to_thread(self._transcribe, source, job.preferences.language)
            project_dir = settings.projects_dir / job.id
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "transcript.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

            await self._update(job, Stage.CURATE, 58, "Construindo narrativas e avaliando candidatos")
            candidates = self._curate(transcript, job)
            if not candidates:
                raise ValueError("Não encontramos fala suficiente para criar cortes coerentes.")
            job.clips = candidates[: job.preferences.clip_count]
            await repository.save(job)

            await self._update(job, Stage.REFINE, 68, "Ajustando os cortes aos limites das frases")
            await self._update(job, Stage.RENDER, 74, "Renderizando vídeos verticais")
            for index, clip in enumerate(job.clips):
                subtitle = project_dir / f"{clip.id}.srt"
                output = project_dir / f"{clip.id}.mp4"
                write_srt(subtitle, transcript, clip.start_ms, clip.end_ms)
                try:
                    await asyncio.to_thread(render_clip, source, output, clip.start_ms, clip.end_ms, job.preferences, subtitle)
                except Exception:
                    await asyncio.to_thread(render_clip, source, output, clip.start_ms, clip.end_ms, job.preferences, None)
                clip.output_url = f"/media/{job.id}/{output.name}"
                progress = 74 + round(24 * (index + 1) / len(job.clips))
                await self._update(job, Stage.RENDER, progress, f"Renderizando corte {index + 1} de {len(job.clips)}")

            await self._update(job, Stage.COMPLETE, 100, f"{len(job.clips)} cortes prontos para revisar")
        except Exception as error:
            job.stage = Stage.FAILED
            job.message = "O processamento foi interrompido"
            job.error = str(error)
            await repository.save(job)

    async def _update(self, job: ProjectJob, stage: Stage, progress: int, message: str) -> None:
        job.stage, job.progress, job.message = stage, progress, message
        await repository.save(job)

    def _transcribe(self, source: Path, language: str) -> list[dict]:
        from faster_whisper import WhisperModel

        if self._asr is None:
            device = settings.asr_device
            if device == "auto":
                device = "cuda" if shutil.which("nvidia-smi") else "cpu"
            compute = settings.asr_compute_type
            if compute == "auto":
                compute = "float16" if device == "cuda" else "int8"
            self._asr = WhisperModel(settings.asr_model, device=device, compute_type=compute)
            self._asr_device = device
        try:
            return self._consume_transcript(self._asr, source, language)
        except RuntimeError as error:
            if self._asr_device != "cuda" or not any(token in str(error).casefold() for token in ("cuda", "cublas", "cudnn")):
                raise
            self._asr = WhisperModel(settings.asr_model, device="cpu", compute_type="int8")
            self._asr_device = "cpu"
            return self._consume_transcript(self._asr, source, language)

    @staticmethod
    def _consume_transcript(model, source: Path, language: str) -> list[dict]:
        segments, _ = model.transcribe(
            str(source), language=None if language == "auto" else language,
            vad_filter=True, word_timestamps=True, beam_size=5,
        )
        return [
            {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip(),
             "words": [{"start": float(word.start), "end": float(word.end), "text": word.word, "probability": word.probability} for word in (segment.words or [])]}
            for segment in segments if segment.text.strip()
        ]

    def _curate(self, transcript: list[dict], job: ProjectJob) -> list[ClipResult]:
        targets = {"short": (18, 34), "medium": (32, 62), "long": (58, 92)}
        minimum, maximum = targets[job.preferences.clip_length]
        candidates: list[ClipResult] = []
        for start_index in range(len(transcript)):
            parts: list[str] = []
            start = transcript[start_index]["start"]
            for end_index in range(start_index, len(transcript)):
                segment = transcript[end_index]
                duration = segment["end"] - start
                parts.append(segment["text"])
                if duration < minimum:
                    continue
                if duration > maximum:
                    break
                text = " ".join(parts)
                score = score_candidate(lexical_signals(text, duration, job.preferences.prompt))
                title = re.sub(r"\s+", " ", text).strip(" -")[:68]
                candidates.append(ClipResult(
                    id=f"clip_{uuid4().hex[:8]}", title=title + ("…" if len(text) > 68 else ""),
                    start_ms=max(0, round(start * 1000) - 180), end_ms=round(segment["end"] * 1000) + 240,
                    quality_score=score,
                ))
                break
        ranked = sorted(candidates, key=lambda candidate: candidate.quality_score, reverse=True)
        selected: list[ClipResult] = []
        for candidate in ranked:
            overlap = any(min(candidate.end_ms, current.end_ms) - max(candidate.start_ms, current.start_ms) > 7_000 for current in selected)
            if not overlap:
                selected.append(candidate)
            if len(selected) >= job.preferences.clip_count:
                break
        return selected

    def _download(self, job: ProjectJob) -> Path:
        import yt_dlp

        output = settings.uploads_dir / f"{job.id}.%(ext)s"
        options = {
            "outtmpl": str(output), "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4", "noplaylist": True, "quiet": True,
            "ffmpeg_location": settings.ffmpeg,
            "js_runtimes": {"node": {"path": shutil.which("node")}},
            "remote_components": ["ejs:npm"],
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(job.source_url, download=True)
            return Path(downloader.prepare_filename(info)).with_suffix(".mp4") if info.get("requested_formats") else Path(downloader.prepare_filename(info))


pipeline = Pipeline()
