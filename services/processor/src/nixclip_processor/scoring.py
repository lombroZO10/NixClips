from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CandidateSignals:
    hook: float
    coherence: float
    value: float
    emotion: float
    visual_interest: float
    prompt_relevance: float
    incomplete_thought_penalty: float = 0
    repetition_penalty: float = 0
    bad_boundary_penalty: float = 0


@dataclass(frozen=True)
class ScoreDetails:
    score: int
    dimensions: dict[str, int]
    penalties: int
    reasons: list[str]


HOOK_CUES = (
    "você", "nunca", "sempre", "ninguém", "o segredo", "o problema", "a verdade",
    "por que", "como", "imagine", "olha", "presta atenção", "sabe o que",
)
VALUE_CUES = (
    "aprenda", "passo", "resultado", "funciona", "melhor", "erro", "importante",
    "significa", "porque", "motivo", "diferença", "precisa", "solução", "exemplo",
)
EMOTION_CUES = (
    "incrível", "absurdo", "surpresa", "medo", "feliz", "difícil", "amo", "odeio",
    "mudou", "chocante", "impossível", "jamais", "acredita",
)
WEAK_STARTS = ("e ", "mas ", "então ", "aí ", "daí ", "porque ", "tipo ", "né ")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_candidate(signals: CandidateSignals) -> int:
    positive = (
        .24 * signals.hook + .25 * signals.coherence + .18 * signals.value
        + .11 * signals.emotion + .12 * signals.visual_interest + .10 * signals.prompt_relevance
    )
    penalty = (
        .15 * signals.incomplete_thought_penalty
        + .09 * signals.repetition_penalty
        + .13 * signals.bad_boundary_penalty
    )
    return round(_clamp(positive - penalty) * 99)


def explain_score(signals: CandidateSignals, prompt_supplied: bool = False) -> ScoreDetails:
    score = score_candidate(signals)
    dimensions = {
        "hook": round(_clamp(signals.hook) * 100),
        "coherence": round(_clamp(signals.coherence) * 100),
        "value": round(_clamp(signals.value) * 100),
        "emotion": round(_clamp(signals.emotion) * 100),
        "delivery": round(_clamp(signals.visual_interest) * 100),
        "relevance": round(_clamp(signals.prompt_relevance) * 100),
    }
    labels = {
        "hook": "Gancho forte", "coherence": "Ideia completa",
        "value": "Alta densidade de valor", "emotion": "Carga emocional",
        "delivery": "Fala clara e dinâmica", "relevance": "Alinhado à direção criativa",
    }
    eligible = ["hook", "coherence", "value", "emotion", "delivery"]
    if prompt_supplied:
        eligible.append("relevance")
    reasons = [labels[key] for key in sorted(eligible, key=dimensions.get, reverse=True) if dimensions[key] >= 62][:3]
    if not reasons:
        reasons = ["Trecho autocontido"]
    penalties = round(100 * _clamp(
        .41 * signals.incomplete_thought_penalty
        + .24 * signals.repetition_penalty
        + .35 * signals.bad_boundary_penalty
    ))
    return ScoreDetails(score=score, dimensions=dimensions, penalties=penalties, reasons=reasons)


def lexical_signals(
    text: str, duration_seconds: float, prompt: str = "", *, pause_before: float = 0,
    pause_after: float = 0, average_confidence: float = .8, audio_energy: float = .5,
    visual_activity: float = .0, face_presence: float = .0, scene_change: float = .0,
) -> CandidateSignals:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    first = normalized[:190]
    words = re.findall(r"\b[\wÀ-ÿ'-]+\b", normalized)
    density = len(words) / max(duration_seconds, 1)
    hook = .38 + .095 * sum(cue in first for cue in HOOK_CUES)
    hook += .10 if "?" in first else 0
    hook += .06 if any(char.isdigit() for char in first) else 0
    ends_cleanly = normalized.endswith((".", "!", "?", "…"))
    starts_weakly = normalized.startswith(WEAK_STARTS)
    coherence = .53 + (.20 if ends_cleanly else 0) + min(.14, pause_after / 5) + min(.10, pause_before / 6)
    if 20 <= duration_seconds <= 78:
        coherence += .08
    value = .44 + .075 * sum(cue in normalized for cue in VALUE_CUES)
    value += .06 if any(marker in normalized for marker in ("primeiro", "segundo", "por isso", "ou seja")) else 0
    emotion = .36 + .085 * sum(cue in normalized for cue in EMOTION_CUES)
    emotion += .07 if "!" in normalized else 0
    # Acoustic emphasis is a useful second modality: energetic delivery often
    # signals a punchline or a strong opinion, while very low energy is usually
    # an intro, pause or tail that should rank lower.
    emotion += .08 * (_clamp(audio_energy) - .5)
    prompt_terms = {term for term in re.findall(r"\b[\wÀ-ÿ'-]+\b", prompt.casefold()) if len(term) > 3}
    prompt_hits = sum(term in normalized for term in prompt_terms)
    prompt_relevance = .68 if not prompt_terms else .30 + .16 * min(prompt_hits, 4)
    density_quality = 1 - min(abs(density - 2.65) / 2.65, 1)
    visual_signal = .45 * _clamp(visual_activity) + .35 * _clamp(face_presence) + .20 * _clamp(scene_change)
    delivery = (
        .27 + .25 * _clamp(average_confidence) + .15 * density_quality
        + .15 * _clamp(audio_energy) + .18 * visual_signal
    )
    trigrams = [tuple(words[index:index + 3]) for index in range(max(0, len(words) - 2))]
    repetition = 0 if not trigrams else 1 - len(set(trigrams)) / len(trigrams)
    boundary_penalty = 0
    if pause_before < .12:
        boundary_penalty += .28
    if pause_after < .12 and not ends_cleanly:
        boundary_penalty += .38
    if normalized.endswith((",", ":", ";")):
        boundary_penalty += .32
    return CandidateSignals(
        hook=_clamp(hook), coherence=_clamp(coherence), value=_clamp(value),
        emotion=_clamp(emotion), visual_interest=_clamp(delivery),
        prompt_relevance=_clamp(prompt_relevance),
        incomplete_thought_penalty=.62 if starts_weakly else 0,
        repetition_penalty=_clamp(repetition * 2.4), bad_boundary_penalty=_clamp(boundary_penalty),
    )


def serialize_signals(signals: CandidateSignals) -> dict[str, float]:
    return {key: round(value, 4) for key, value in asdict(signals).items()}
