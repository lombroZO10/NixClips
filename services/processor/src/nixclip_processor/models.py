from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


class Stage(str, Enum):
    PENDING = "pending"
    IMPORT = "import"
    ANALYZE = "analyze"
    CURATE = "curate"
    REFINE = "refine"
    RENDER = "render"
    COMPLETE = "complete"
    FAILED = "failed"


class Preferences(ApiModel):
    language: Literal["auto", "pt", "en", "es"] = "auto"
    clip_length: Literal["short", "medium", "long"] = "medium"
    aspect_ratio: Literal["9:16", "1:1", "16:9", "4:5"] = "9:16"
    clip_count: int = Field(default=10, ge=1, le=20)
    prompt: str = Field(default="", max_length=1000)
    captions: bool = True
    auto_reframe: bool = True
    brand_template: dict[str, Any] = Field(default_factory=dict)


class MediaSummary(ApiModel):
    duration_ms: int
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None = None


class ScoreBreakdown(ApiModel):
    hook: int = Field(ge=0, le=100)
    coherence: int = Field(ge=0, le=100)
    value: int = Field(ge=0, le=100)
    emotion: int = Field(ge=0, le=100)
    delivery: int = Field(ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    penalties: int = Field(default=0, ge=0, le=100)


class ClipResult(ApiModel):
    id: str
    title: str
    start_ms: int
    end_ms: int
    quality_score: int
    score_breakdown: ScoreBreakdown | None = None
    reasons: list[str] = Field(default_factory=list)
    transcript_excerpt: str | None = None
    reframe_mode: Literal["face-aware", "center", "fit"] | None = None
    output_url: str | None = None


class ProjectJob(ApiModel):
    id: str
    title: str
    stage: Stage = Stage.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    message: str = "Aguardando processamento"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_name: str | None = None
    source_path: str | None = None
    source_url: str | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    media: MediaSummary | None = None
    clips: list[ClipResult] = Field(default_factory=list)
    error: str | None = None


class UrlProjectRequest(ApiModel):
    url: HttpUrl
    preferences: Preferences = Field(default_factory=Preferences)
