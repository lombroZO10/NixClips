from __future__ import annotations

import json

import aiosqlite

from .config import settings
from .models import ProjectJob


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


class ProjectRepository:
    async def initialize(self) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        settings.projects_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(settings.database_path) as database:
            await database.execute(SCHEMA)
            await database.execute("CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC)")
            await database.commit()

    async def save(self, job: ProjectJob) -> None:
        payload = job.model_dump_json(by_alias=False)
        async with aiosqlite.connect(settings.database_path) as database:
            await database.execute(
                """INSERT INTO projects(id, payload, created_at, updated_at) VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=datetime('now')""",
                (job.id, payload, job.created_at.isoformat()),
            )
            await database.commit()

    async def get(self, project_id: str) -> ProjectJob | None:
        async with aiosqlite.connect(settings.database_path) as database:
            cursor = await database.execute("SELECT payload FROM projects WHERE id = ?", (project_id,))
            row = await cursor.fetchone()
        return ProjectJob.model_validate(json.loads(row[0])) if row else None

    async def list(self, limit: int = 30) -> list[ProjectJob]:
        async with aiosqlite.connect(settings.database_path) as database:
            cursor = await database.execute("SELECT payload FROM projects ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
        return [ProjectJob.model_validate(json.loads(row[0])) for row in rows]

    async def delete(self, project_id: str) -> None:
        async with aiosqlite.connect(settings.database_path) as database:
            await database.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            await database.commit()


repository = ProjectRepository()
