from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import uuid4

from .models import ClipResult, Preferences, ScoreBreakdown
from .scoring import explain_score, lexical_signals


@dataclass(frozen=True)
class EditorialCandidate:
    clip: ClipResult
    text: str
    selection_score: float


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -")


def _word_confidence(segments: list[dict]) -> float:
    probabilities = [
        float(word.get("probability", .8))
        for segment in segments for word in segment.get("words", [])
        if word.get("probability") is not None
    ]
    return sum(probabilities) / len(probabilities) if probabilities else .8


def _title(text: str) -> str:
    clean = _clean(text)
    sentence = re.split(r"(?<=[.!?])\s+", clean, maxsplit=1)[0]
    chosen = sentence if len(sentence) >= 24 else clean
    return chosen[:72].rstrip(" ,:;-") + ("…" if len(chosen) > 72 else "")


def _pause_before(transcript: list[dict], index: int) -> float:
    if index == 0:
        return float(transcript[index]["start"])
    return max(0, float(transcript[index]["start"]) - float(transcript[index - 1]["end"]))


def _pause_after(transcript: list[dict], index: int) -> float:
    if index + 1 >= len(transcript):
        return 1.2
    return max(0, float(transcript[index + 1]["start"]) - float(transcript[index]["end"]))


def _timeline_overlap(first: ClipResult, second: ClipResult) -> float:
    overlap = max(0, min(first.end_ms, second.end_ms) - max(first.start_ms, second.start_ms))
    shorter = max(1, min(first.end_ms - first.start_ms, second.end_ms - second.start_ms))
    return overlap / shorter


def _text_similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, first.casefold(), second.casefold()).ratio()


def build_candidates(transcript: list[dict], preferences: Preferences) -> list[EditorialCandidate]:
    targets = {"short": (16, 30, 23), "medium": (28, 58, 42), "long": (52, 88, 68)}
    minimum, maximum, ideal = targets[preferences.clip_length]
    candidates: list[EditorialCandidate] = []
    for start_index, first_segment in enumerate(transcript):
        start = float(first_segment["start"])
        before = _pause_before(transcript, start_index)
        for end_index in range(start_index, len(transcript)):
            last_segment = transcript[end_index]
            duration = float(last_segment["end"]) - start
            if duration < minimum:
                continue
            if duration > maximum:
                break
            chosen_segments = transcript[start_index:end_index + 1]
            text = _clean(" ".join(str(segment["text"]) for segment in chosen_segments))
            if len(text.split()) < 24:
                continue
            after = _pause_after(transcript, end_index)
            signals = lexical_signals(
                text, duration, preferences.prompt, pause_before=before, pause_after=after,
                average_confidence=_word_confidence(chosen_segments),
            )
            details = explain_score(signals, bool(preferences.prompt.strip()))
            duration_fit = max(0, 1 - abs(duration - ideal) / max(ideal, 1))
            boundary_bonus = min(before, 1.2) * 1.5 + min(after, 1.2) * 1.8
            start_padding = min(220, round(before * 420))
            end_padding = min(280, round(after * 420))
            clip = ClipResult(
                id=f"clip_{uuid4().hex[:8]}", title=_title(text),
                start_ms=max(0, round(start * 1000) - start_padding),
                end_ms=round(float(last_segment["end"]) * 1000) + end_padding,
                quality_score=details.score,
                score_breakdown=ScoreBreakdown(**details.dimensions, penalties=details.penalties),
                reasons=details.reasons,
                transcript_excerpt=text[:360] + ("…" if len(text) > 360 else ""),
            )
            candidates.append(EditorialCandidate(clip=clip, text=text, selection_score=details.score + duration_fit * 5 + boundary_bonus))
    return candidates


def select_diverse(candidates: list[EditorialCandidate], count: int) -> list[ClipResult]:
    ranked = sorted(candidates, key=lambda item: item.selection_score, reverse=True)
    selected: list[EditorialCandidate] = []
    for candidate in ranked:
        if any(
            _timeline_overlap(candidate.clip, current.clip) > .34
            or _text_similarity(candidate.text, current.text) > .76
            for current in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= count:
            break
    return [candidate.clip for candidate in selected]


def curate_transcript(transcript: list[dict], preferences: Preferences) -> list[ClipResult]:
    return select_diverse(build_candidates(transcript, preferences), preferences.clip_count)
