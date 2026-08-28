from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .config import settings
from .curation import curate_transcript
from .media import probe_media, render_clip, write_srt
from .models import ProjectJob, Stage
from .repository import repository
from .visual import analyze_video, enrich_transcript
from .advanced import detect_objects, diarize, enrich_with_advanced_signals


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
            if job.source_url and (not job.source_path or not Path(job.source_path).exists()):
                await self._update(job, Stage.IMPORT, 4, "Baixando o vídeo original")
                job.source_path = str(await asyncio.to_thread(self._download, job))

            source = Path(job.source_path or "")
            await self._update(job, Stage.IMPORT, 10, "Inspecionando faixas, duração e resolução")
            job.media = await asyncio.to_thread(probe_media, source)
            await repository.save(job)

            project_dir = settings.projects_dir / job.id
            project_dir.mkdir(parents=True, exist_ok=True)
            transcript_path = project_dir / "transcript.json"
            if transcript_path.exists():
                await self._update(job, Stage.ANALYZE, 46, "Reutilizando a transcrição alinhada")
                transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
            else:
                await self._update(job, Stage.ANALYZE, 22, "Preparando o áudio para transcrição")
                transcript_task = asyncio.create_task(
                    asyncio.to_thread(self._transcribe, source, job.preferences.language, project_dir / "analysis-audio.wav")
                )
                started_at = time.monotonic()
                while not transcript_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(transcript_task), timeout=5)
                    except asyncio.TimeoutError:
                        elapsed = int(time.monotonic() - started_at)
                        progress = min(45, 24 + max(0, elapsed // 12))
                        await self._update(
                            job, Stage.ANALYZE, progress,
                            f"Transcrevendo e alinhando a fala · {elapsed // 60:02d}:{elapsed % 60:02d}",
                        )
                transcript = await transcript_task
                transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

            visual_path = project_dir / "visual.json"
            if visual_path.exists():
                visual = json.loads(visual_path.read_text(encoding="utf-8"))
            else:
                await self._update(job, Stage.ANALYZE, 46, "Analisando cenas, movimento e rostos")
                visual_task = asyncio.create_task(asyncio.to_thread(
                    analyze_video, source, job.media.duration_ms if job.media else 0, settings.visual_sample_fps,
                ))
                while not visual_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(visual_task), timeout=5)
                    except asyncio.TimeoutError:
                        await self._update(job, Stage.ANALYZE, 50, "Analisando cenas, movimento e rostos")
                visual = await visual_task
                visual_path.write_text(json.dumps(visual, ensure_ascii=False), encoding="utf-8")
            transcript = enrich_transcript(transcript, visual)
            advanced_path = project_dir / "advanced.json"
            if advanced_path.exists():
                advanced = json.loads(advanced_path.read_text(encoding="utf-8"))
            else:
                await self._update(job, Stage.ANALYZE, 52, "Rastreando objetos e identificando falantes")
                object_task = asyncio.create_task(asyncio.to_thread(
                    detect_objects, source, job.media.duration_ms if job.media else 0,
                ))
                await object_task
                audio_path = project_dir / "analysis-audio.wav"
                speaker_task = asyncio.create_task(asyncio.to_thread(diarize, audio_path)) if audio_path.exists() else None
                objects = object_task.result()
                speakers = await speaker_task if speaker_task else {"backend": "unavailable", "segments": []}
                advanced = {"objects": objects, "speakers": speakers}
                advanced_path.write_text(json.dumps(advanced, ensure_ascii=False), encoding="utf-8")
            transcript = enrich_with_advanced_signals(
                transcript, advanced.get("objects", {}), advanced.get("speakers", {}),
            )
            transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

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
                    clip.reframe_mode = await asyncio.to_thread(
                        render_clip, source, output, clip.start_ms, clip.end_ms, job.preferences, subtitle,
                    )
                except Exception:
                    clip.reframe_mode = await asyncio.to_thread(
                        render_clip, source, output, clip.start_ms, clip.end_ms, job.preferences, None,
                    )
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

    def _transcribe(self, source: Path, language: str, audio_cache: Path | None = None) -> list[dict]:
        from faster_whisper import WhisperModel

        if self._asr is None:
            requested_device = settings.asr_device
            attempts = [(requested_device, settings.asr_compute_type)] if requested_device != "auto" else [
                ("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8"),
            ]
            last_error: Exception | None = None
            for device, compute in attempts:
                if compute == "auto":
                    compute = "float16" if device == "cuda" else "int8"
                try:
                    self._asr = WhisperModel(
                        settings.asr_model, device=device, compute_type=compute,
                        cpu_threads=settings.asr_cpu_threads, num_workers=settings.asr_num_workers,
                    )
                    self._asr_device = device
                    break
                except (RuntimeError, ValueError) as error:
                    last_error = error
            if self._asr is None:
                raise RuntimeError(f"Não foi possível iniciar o motor de transcrição: {last_error}")
        try:
            return self._consume_transcript(self._asr, source, language, audio_cache)
        except RuntimeError as error:
            if self._asr_device != "cuda" or not any(token in str(error).casefold() for token in ("cuda", "cublas", "cudnn")):
                raise
            self._asr = WhisperModel(
                settings.asr_model, device="cpu", compute_type="int8",
                cpu_threads=settings.asr_cpu_threads, num_workers=settings.asr_num_workers,
            )
            self._asr_device = "cpu"
            return self._consume_transcript(self._asr, source, language, audio_cache)

    @staticmethod
    def _consume_transcript(model, source: Path, language: str, audio_cache: Path | None = None) -> list[dict]:
        # Whisper does not need the 4K video stream. Converting to a small, local
        # 16 kHz mono WAV makes long YouTube imports dramatically faster and more
        # predictable on CPU-only machines.
        descriptor, temporary_name = tempfile.mkstemp(prefix="nixclip-asr-", suffix=".wav")
        os.close(descriptor)
        temporary_audio = Path(temporary_name)
        try:
            audio_target = audio_cache or temporary_audio
            audio_target.parent.mkdir(parents=True, exist_ok=True)
            if not audio_target.exists():
                subprocess.run(
                    [settings.ffmpeg, "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_target)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )
            segments, _ = model.transcribe(
                str(audio_target), language=None if language == "auto" else language,
                vad_filter=True, word_timestamps=True, beam_size=1,
                condition_on_previous_text=False,
            )
            transcript = [
                {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip(),
                 "words": [{"start": float(word.start), "end": float(word.end), "text": word.word, "probability": word.probability} for word in (segment.words or [])]}
                for segment in segments if segment.text.strip()
            ]
            for segment in transcript:
                segment["audio_energy"] = _audio_energy(audio_target, segment["start"], segment["end"])
            return transcript
        finally:
            if audio_cache is None:
                temporary_audio.unlink(missing_ok=True)

    def _curate(self, transcript: list[dict], job: ProjectJob):
        return curate_transcript(transcript, job.preferences)

    def _download(self, job: ProjectJob) -> Path:
        import yt_dlp

        output = settings.uploads_dir / f"{job.id}.%(ext)s"
        options = {
            # 720p is enough for the vertical reframing output and avoids
            # pulling multi-gigabyte 4K sources before analysis even starts.
            "outtmpl": str(output), "format": "bv*[height<=720]+ba/b[height<=720]/b",
            "merge_output_format": "mp4", "noplaylist": True, "quiet": True,
            "ffmpeg_location": settings.ffmpeg,
            "js_runtimes": {"node": {"path": shutil.which("node")}},
            "remote_components": ["ejs:npm"],
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(job.source_url, download=True)
            return Path(downloader.prepare_filename(info)).with_suffix(".mp4") if info.get("requested_formats") else Path(downloader.prepare_filename(info))


pipeline = Pipeline()


def _audio_energy(path: Path, start: float, end: float) -> float:
    """Return a cheap normalized RMS estimate for editorial scoring."""
    try:
        with wave.open(str(path), "rb") as audio:
            rate = audio.getframerate()
            width = audio.getsampwidth()
            audio.setpos(max(0, int(start * rate)))
            frames = audio.readframes(max(1, int((end - start) * rate)))
        if not frames or width != 2:
            return .5
        import struct
        samples = struct.unpack(f"<{len(frames) // 2}h", frames[: len(frames) // 2 * 2])
        if not samples:
            return .5
        rms = (sum(sample * sample for sample in samples) / len(samples)) ** .5 / 32768
        return max(0.0, min(1.0, rms * 4.5))
    except (OSError, ValueError, EOFError):
        return .5
