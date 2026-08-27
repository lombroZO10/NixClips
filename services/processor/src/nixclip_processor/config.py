from __future__ import annotations

import shutil
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROCESSOR_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = PROCESSOR_DIR.parents[1]


def bundled_binary(package: str, executable: str) -> str | None:
    candidate = REPOSITORY_DIR / "node_modules" / package / executable
    if candidate.exists():
        return str(candidate)
    return shutil.which(Path(executable).stem)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROCESSOR_DIR / ".env", env_prefix="NIXCLIP_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8788
    data_dir: Path = PROCESSOR_DIR / "data"
    asr_model: str = "small"
    asr_device: str = "auto"
    asr_compute_type: str = "auto"
    allowed_origins: str = "http://localhost:3000"
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "nixclip.sqlite3"

    @property
    def ffmpeg(self) -> str:
        value = self.ffmpeg_path or bundled_binary("ffmpeg-static", "ffmpeg.exe")
        if not value:
            raise RuntimeError("FFmpeg não foi encontrado. Instale as dependências do workspace.")
        return value

    @property
    def ffprobe(self) -> str:
        value = self.ffprobe_path or bundled_binary("ffprobe-static", "bin/win32/x64/ffprobe.exe")
        if not value:
            raise RuntimeError("FFprobe não foi encontrado. Instale as dependências do workspace.")
        return value

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
