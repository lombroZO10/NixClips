from __future__ import annotations

import shutil
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROCESSOR_DIR = Path(__file__).resolve().parents[2]
# In Docker the processor is installed directly under /app; locally it lives
# under services/processor and needs the workspace root for bundled binaries.
REPOSITORY_DIR = (
    PROCESSOR_DIR.parents[1]
    if len(PROCESSOR_DIR.parents) > 1 and (PROCESSOR_DIR / "pyproject.toml").exists()
    else PROCESSOR_DIR
)


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
    asr_cpu_threads: int = max(1, (os.cpu_count() or 4) // 2)
    asr_num_workers: int = 1
    analysis_max_width: int = 1280
    visual_sample_fps: float = 1.5
    yolo_model: str = "yolo11n.pt"
    hf_token: str = ""
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://nixclip.fnxtutors.chatgpt.site,https://nixclips-ruby.vercel.app"
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    youtube_cookie_file: Path | None = None
    youtube_player_clients: str = "mweb,web_embedded,tv,android"
    youtube_pot_provider_url: str = "http://127.0.0.1:4416"
    youtube_download_concurrency: int = 1
    youtube_download_delay: float = 15.0
    youtube_sleep_requests: float = 5.0
    youtube_limit_rate: int = 2_000_000
    youtube_max_attempts: int = 6
    youtube_backoff_base: float = 5.0
    youtube_backoff_cap: float = 120.0
    youtube_rate_limit_cooldown: float = 600.0

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

    @property
    def youtube_clients(self) -> list[str]:
        return [client.strip() for client in self.youtube_player_clients.split(",") if client.strip()]


settings = Settings()
