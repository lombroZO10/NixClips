from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models import Preferences, ProjectJob, Stage, UrlProjectRequest
from .pipeline import pipeline
from .repository import repository


@asynccontextmanager
async def lifespan(_: FastAPI):
    await repository.initialize()
    for job in await repository.list(limit=100):
        if job.stage not in {Stage.COMPLETE, Stage.FAILED}:
            asyncio.create_task(pipeline.run(job.id))
    yield


app = FastAPI(title="NixClip Processor", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
    allow_private_network=True,
)
settings.projects_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.projects_dir), name="media")


def public_job(job: ProjectJob) -> dict:
    return job.model_dump(mode="json", by_alias=True, exclude={"source_path", "source_url", "preferences"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "nixclip-processor", "version": app.version}


@app.post("/api/v1/projects/upload", status_code=202)
async def create_upload_project(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    preferences: str = Form("{}"),
) -> dict:
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
        raise HTTPException(415, "Formato não suportado. Use MP4, MOV, MKV ou WebM.")
    try:
        parsed_preferences = Preferences.model_validate(json.loads(preferences))
    except Exception as error:
        raise HTTPException(422, "As configurações do projeto são inválidas.") from error

    project_id = uuid4().hex
    destination = settings.uploads_dir / f"{project_id}{suffix}"
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024 * 8):
                target.write(chunk)
    finally:
        await file.close()

    job = ProjectJob(
        id=project_id, title=Path(file.filename or "Novo projeto").stem,
        stage=Stage.PENDING, progress=1, message="Projeto recebido e adicionado à fila",
        source_name=file.filename, source_path=str(destination), preferences=parsed_preferences,
    )
    await repository.save(job)
    background_tasks.add_task(pipeline.run, job.id)
    return public_job(job)


@app.post("/api/v1/projects/url", status_code=202)
async def create_url_project(request: UrlProjectRequest, background_tasks: BackgroundTasks) -> dict:
    project_id = uuid4().hex
    job = ProjectJob(
        id=project_id, title="Vídeo importado por link", stage=Stage.PENDING, progress=1,
        message="Link recebido e adicionado à fila", source_name=str(request.url),
        source_url=str(request.url), preferences=request.preferences,
    )
    await repository.save(job)
    background_tasks.add_task(pipeline.run, job.id)
    return public_job(job)


@app.get("/api/v1/projects")
async def list_projects() -> list[dict]:
    return [public_job(job) for job in await repository.list()]


@app.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    job = await repository.get(project_id)
    if not job:
        raise HTTPException(404, "Projeto não encontrado.")
    return public_job(job)


@app.post("/api/v1/projects/{project_id}/retry", status_code=202)
async def retry_project(project_id: str, background_tasks: BackgroundTasks) -> dict:
    job = await repository.get(project_id)
    if not job:
        raise HTTPException(404, "Projeto não encontrado.")
    job.stage, job.progress, job.message, job.error = Stage.PENDING, 1, "Projeto reenviado para a fila", None
    await repository.save(job)
    background_tasks.add_task(pipeline.run, job.id)
    return public_job(job)
