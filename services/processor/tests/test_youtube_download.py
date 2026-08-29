from pathlib import Path

import pytest

from nixclip_processor.config import Settings
from nixclip_processor.youtube_download import (
    FailureKind,
    YoutubeDownloadError,
    YoutubeDownloader,
    classify_download_error,
    exponential_backoff,
    inspect_cookie_file,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("HTTP Error 429: Too Many Requests", FailureKind.RATE_LIMIT),
        ("Sign in to confirm you're not a bot", FailureKind.RATE_LIMIT),
        ("HTTP Error 403: Forbidden", FailureKind.TRANSIENT),
        ("Sign in to confirm your age", FailureKind.AUTH),
        ("Private video", FailureKind.PERMANENT),
        ("Connection reset by peer", FailureKind.TRANSIENT),
    ],
)
def test_error_classification(message: str, expected: FailureKind) -> None:
    assert classify_download_error(message) is expected


def test_cookie_inspection_accepts_a_non_expired_netscape_cookie(tmp_path: Path) -> None:
    cookie = tmp_path / "cookies.txt"
    cookie.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2000000000\tSID\tsecret\n",
        encoding="utf-8",
    )
    result = inspect_cookie_file(cookie, now=1_900_000_000)
    assert result.valid is True
    assert result.expires_at == 2_000_000_000


def test_cookie_inspection_rejects_expired_and_malformed_files(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.txt"
    malformed.write_text("SID=secret", encoding="utf-8")
    assert inspect_cookie_file(malformed).reason == "invalid_netscape_header"

    expired = tmp_path / "expired.txt"
    expired.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t100\tSID\tsecret\n",
        encoding="utf-8",
    )
    assert inspect_cookie_file(expired, now=101).reason == "expired_or_empty"


def test_backoff_is_bounded_and_has_jitter() -> None:
    assert exponential_backoff(1, 10, 60, random_value=0) == 7.5
    assert exponential_backoff(5, 10, 60, random_value=1) == 60


def make_settings(**overrides) -> Settings:
    defaults = {
        "youtube_cookie_file": None,
        "youtube_pot_provider_url": "",
        "youtube_player_clients": "mweb,web_embedded",
        "youtube_download_delay": 0,
        "youtube_sleep_requests": 0,
        "youtube_max_attempts": 3,
        "youtube_backoff_base": 0,
        "youtube_backoff_cap": 0,
        "youtube_rate_limit_cooldown": 0,
    }
    return Settings(_env_file=None, **(defaults | overrides))


def test_transient_failure_falls_back_to_next_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = YoutubeDownloader(make_settings())
    clients: list[str] = []

    def fake_download(url: str, output: Path, ffmpeg: str, client: str) -> Path:
        clients.append(client)
        if len(clients) == 1:
            raise RuntimeError("HTTP Error 403: Forbidden")
        return tmp_path / "result.mp4"

    monkeypatch.setattr(manager, "_download_once", fake_download)
    result = manager.download("https://example.invalid/video", tmp_path / "x.%(ext)s", "ffmpeg")
    assert result.name == "result.mp4"
    assert clients == ["mweb", "web_embedded"]
    assert manager.health.snapshot()["status"] == "healthy"


def test_permanent_failure_does_not_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = YoutubeDownloader(make_settings())
    calls = 0

    def fake_download(url: str, output: Path, ffmpeg: str, client: str) -> Path:
        nonlocal calls
        calls += 1
        raise RuntimeError("Private video")

    monkeypatch.setattr(manager, "_download_once", fake_download)
    with pytest.raises(YoutubeDownloadError) as captured:
        manager.download("https://example.invalid/video", tmp_path / "x.%(ext)s", "ffmpeg")
    assert captured.value.kind is FailureKind.PERMANENT
    assert calls == 1


def test_rate_limit_opens_circuit_before_resuming(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[float] = []
    manager = YoutubeDownloader(make_settings(youtube_rate_limit_cooldown=10), sleep=sleeps.append)
    calls = 0

    def fake_download(url: str, output: Path, ffmpeg: str, client: str) -> Path:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return tmp_path / "result.mp4"

    monkeypatch.setattr(manager, "_download_once", fake_download)
    manager.download("https://example.invalid/video", tmp_path / "x.%(ext)s", "ffmpeg")
    assert calls == 2
    assert any(delay >= 9 for delay in sleeps)
    assert manager.health.snapshot()["status"] == "healthy"
