from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import socket
import tempfile
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .config import Settings, settings


logger = logging.getLogger("nixclip.youtube")
logger.setLevel(logging.INFO)


class FailureKind(str, Enum):
    RATE_LIMIT = "rate_limit"
    AUTH = "authentication"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


class YoutubeDownloadError(RuntimeError):
    def __init__(self, message: str, kind: FailureKind, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


@dataclass(frozen=True)
class CookieInspection:
    configured: bool
    valid: bool
    reason: str
    expires_at: int | None = None


_RATE_LIMIT_MARKERS = (
    "http error 429", "too many requests", "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot", "unusual traffic", "not a bot",
)
_AUTH_MARKERS = (
    "login required", "sign in to confirm your age", "members-only", "members only",
    "authentication required", "cookies are no longer valid", "account has been disabled",
)
_PERMANENT_MARKERS = (
    "video unavailable", "private video", "this video has been removed", "copyright",
    "not available in your country", "geo-restricted", "unsupported url", "does not exist",
)
_TRANSIENT_MARKERS = (
    "http error 403", "forbidden", "timed out", "timeout", "connection reset",
    "connection aborted", "temporary failure", "remote end closed connection", "network is unreachable",
)


def classify_download_error(error: BaseException | str) -> FailureKind:
    message = str(error).casefold()
    if any(marker in message for marker in _RATE_LIMIT_MARKERS):
        return FailureKind.RATE_LIMIT
    if any(marker in message for marker in _AUTH_MARKERS):
        return FailureKind.AUTH
    if any(marker in message for marker in _PERMANENT_MARKERS):
        return FailureKind.PERMANENT
    if any(marker in message for marker in _TRANSIENT_MARKERS):
        return FailureKind.TRANSIENT
    # Extractor failures often change wording. A bounded retry is safer than
    # permanently rejecting an otherwise valid URL.
    return FailureKind.TRANSIENT


def inspect_cookie_file(path: Path | None, now: int | None = None) -> CookieInspection:
    if path is None:
        return CookieInspection(False, True, "not_configured")
    if not path.is_file():
        return CookieInspection(True, False, "file_missing")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return CookieInspection(True, False, "unreadable")
    if not lines or lines[0].strip() not in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}:
        return CookieInspection(True, False, "invalid_netscape_header")
    current = int(time.time() if now is None else now)
    expirations: list[int] = []
    has_session_cookie = False
    for line in lines[1:]:
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        normalized = line.removeprefix("#HttpOnly_")
        fields = normalized.split("\t")
        if len(fields) < 7 or "youtube.com" not in fields[0].casefold():
            continue
        try:
            expires = int(fields[4])
        except ValueError:
            continue
        if expires == 0:
            has_session_cookie = True
        elif expires > current:
            expirations.append(expires)
    if has_session_cookie or expirations:
        return CookieInspection(True, True, "ok", min(expirations) if expirations else None)
    return CookieInspection(True, False, "expired_or_empty")


def exponential_backoff(attempt: int, base: float, cap: float, random_value: float | None = None) -> float:
    jitter = random.random() if random_value is None else random_value
    return min(cap, base * (2 ** max(0, attempt - 1)) * (0.75 + 0.5 * jitter))


def _safe_error(error: BaseException | str) -> str:
    message = re.sub(r"https?://\S+", "[url]", str(error))
    return message[:500]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def writable_cookie_copy(source: Path):
    """Give yt-dlp a private writable jar while keeping the mounted secret read-only."""
    descriptor, temporary_name = tempfile.mkstemp(prefix="nixclip-youtube-", suffix=".cookies.txt")
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        temporary.chmod(0o600)
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


class DownloadHealth:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, object] = {
            "status": "idle", "consecutive_failures": 0, "last_success_at": None,
            "last_failure_at": None, "last_error_kind": None, "last_error": None,
            "last_client": None, "circuit_open_until": None,
        }

    def begin(self, client: str) -> None:
        with self._lock:
            self._state.update(status="downloading", last_client=client)

    def succeed(self, client: str) -> None:
        with self._lock:
            self._state.update(
                status="healthy", consecutive_failures=0, last_success_at=_utc_now(),
                last_error_kind=None, last_error=None, last_client=client, circuit_open_until=None,
            )

    def fail(self, kind: FailureKind, error: BaseException | str, client: str) -> None:
        with self._lock:
            self._state.update(
                status="degraded", consecutive_failures=int(self._state["consecutive_failures"]) + 1,
                last_failure_at=_utc_now(), last_error_kind=kind.value,
                last_error=_safe_error(error), last_client=client,
            )

    def open_circuit(self, seconds: float) -> None:
        with self._lock:
            self._state.update(status="cooldown", circuit_open_until=time.time() + seconds)

    def wait_seconds(self) -> float:
        with self._lock:
            until = self._state.get("circuit_open_until")
            return max(0.0, float(until) - time.time()) if until else 0.0

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            result = dict(self._state)
        wait = self.wait_seconds()
        result["cooldown_seconds"] = round(wait)
        if result["status"] == "cooldown" and wait <= 0:
            result["status"] = "degraded"
        return result


class YoutubeDownloader:
    def __init__(
        self,
        config: Settings = settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.health = DownloadHealth()
        self._sleep = sleep
        self._semaphore = threading.BoundedSemaphore(max(1, config.youtube_download_concurrency))
        self._request_lock = threading.Lock()
        self._last_download_started = 0.0

    def download(self, url: str, output_template: Path, ffmpeg: str) -> Path:
        cookie = inspect_cookie_file(self.config.youtube_cookie_file)
        if not cookie.valid:
            message = f"cookies.txt inválido ou vencido ({cookie.reason}); exporte uma sessão válida novamente"
            self.health.fail(FailureKind.AUTH, message, "none")
            raise YoutubeDownloadError(message, FailureKind.AUTH)
        clients = self.config.youtube_clients or ["mweb"]
        last_error: YoutubeDownloadError | None = None
        with self._semaphore:
            for attempt in range(1, max(1, self.config.youtube_max_attempts) + 1):
                self._wait_for_circuit()
                client = clients[(attempt - 1) % len(clients)]
                self._respect_download_delay()
                self.health.begin(client)
                self._log("download_attempt", attempt=attempt, client=client)
                try:
                    result = self._download_once(url, output_template, ffmpeg, client)
                except Exception as error:
                    kind = classify_download_error(error)
                    last_error = YoutubeDownloadError(_safe_error(error), kind)
                    self.health.fail(kind, error, client)
                    self._log("download_failure", level=logging.WARNING, attempt=attempt, client=client, kind=kind.value, error=_safe_error(error))
                    if kind in {FailureKind.PERMANENT, FailureKind.AUTH}:
                        raise last_error from error
                    if kind is FailureKind.RATE_LIMIT:
                        self.health.open_circuit(self.config.youtube_rate_limit_cooldown)
                        self._log("rate_limit_cooldown", level=logging.WARNING, seconds=self.config.youtube_rate_limit_cooldown)
                    elif attempt < self.config.youtube_max_attempts:
                        delay = exponential_backoff(attempt, self.config.youtube_backoff_base, self.config.youtube_backoff_cap)
                        self._log("retry_backoff", seconds=round(delay, 2), next_client=clients[attempt % len(clients)])
                        self._sleep(delay)
                    continue
                self.health.succeed(client)
                self._log("download_success", client=client)
                return result
        assert last_error is not None
        raise last_error

    def _wait_for_circuit(self) -> None:
        wait = self.health.wait_seconds()
        if wait > 0:
            self._log("circuit_wait", level=logging.WARNING, seconds=round(wait, 2))
            self._sleep(wait)

    def _respect_download_delay(self) -> None:
        with self._request_lock:
            remaining = self.config.youtube_download_delay - (time.monotonic() - self._last_download_started)
            if remaining > 0:
                self._sleep(remaining)
            self._last_download_started = time.monotonic()

    def _download_once(self, url: str, output_template: Path, ffmpeg: str, client: str) -> Path:
        import yt_dlp

        extractor_args: dict[str, dict[str, list[str]]] = {
            "youtube": {"player_client": [client]},
        }
        if self.config.youtube_pot_provider_url:
            extractor_args["youtubepot-bgutilhttp"] = {"base_url": [self.config.youtube_pot_provider_url]}
        runtimes = {
            name: {"path": path}
            for name, path in (("deno", shutil.which("deno")), ("node", shutil.which("node")))
            if path
        }
        options: dict[str, object] = {
            "outtmpl": str(output_template),
            "format": "bv*[height<=720]+ba/b[height<=720]/b",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": False,
            "ffmpeg_location": ffmpeg,
            "js_runtimes": runtimes,
            "remote_components": ["ejs:npm"],
            "extractor_args": extractor_args,
            "sleep_interval_requests": self.config.youtube_sleep_requests,
            "ratelimit": self.config.youtube_limit_rate,
            "retries": 2,
            "fragment_retries": 2,
            "file_access_retries": 2,
            "socket_timeout": 30,
        }
        with ExitStack() as resources:
            # Android's Innertube client does not support account cookies. It
            # is retained only as a public-video fallback. Other clients get a
            # disposable copy because yt-dlp persists cookie changes on close.
            if self.config.youtube_cookie_file and client != "android":
                cookiefile = resources.enter_context(writable_cookie_copy(self.config.youtube_cookie_file))
                options["cookiefile"] = str(cookiefile)
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                prepared = Path(downloader.prepare_filename(info))
                result = prepared.with_suffix(".mp4") if info.get("requested_formats") else prepared
        if not result.exists():
            temporary_suffixes = {".part", ".ytdl", ".temp"}
            matches = sorted(
                (
                    path for path in result.parent.glob(f"{result.stem}.*")
                    if path.is_file() and path.suffix.casefold() not in temporary_suffixes
                ),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if matches:
                return matches[0]
            raise RuntimeError("yt-dlp finalizou sem produzir o arquivo esperado")
        return result

    def provider_reachable(self, timeout: float = 0.25) -> bool | None:
        if not self.config.youtube_pot_provider_url:
            return None
        parsed = urlparse(self.config.youtube_pot_provider_url)
        try:
            with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _log(event: str, level: int = logging.INFO, **fields: object) -> None:
        logger.log(level, json.dumps({"event": event, "timestamp": _utc_now(), **fields}, ensure_ascii=False, sort_keys=True))


youtube_downloader = YoutubeDownloader()
