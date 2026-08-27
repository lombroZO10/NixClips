from __future__ import annotations

from dataclasses import dataclass


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


def score_candidate(signals: CandidateSignals) -> int:
    positive = (
        .26 * signals.hook + .24 * signals.coherence + .18 * signals.value
        + .12 * signals.emotion + .10 * signals.visual_interest + .10 * signals.prompt_relevance
    )
    penalty = .16 * signals.incomplete_thought_penalty + .10 * signals.repetition_penalty + .12 * signals.bad_boundary_penalty
    return round(max(0.0, min(1.0, positive - penalty)) * 99)


HOOK_CUES = ("você", "nunca", "sempre", "ninguém", "o segredo", "o problema", "a verdade", "por que", "como")
VALUE_CUES = ("aprenda", "passo", "resultado", "funciona", "melhor", "erro", "importante", "significa", "porque")
EMOTION_CUES = ("incrível", "absurdo", "surpresa", "medo", "feliz", "difícil", "amo", "odeio", "mudou")


def lexical_signals(text: str, duration_seconds: float, prompt: str = "") -> CandidateSignals:
    normalized = text.casefold().strip()
    first = normalized[:180]
    hook = min(.95, .42 + .11 * sum(cue in first for cue in HOOK_CUES) + (.09 if "?" in first else 0))
    coherence = .86 if normalized.endswith((".", "!", "?")) else .58
    if duration_seconds < 12 or duration_seconds > 100:
        coherence -= .18
    value = min(.94, .48 + .09 * sum(cue in normalized for cue in VALUE_CUES))
    emotion = min(.92, .40 + .10 * sum(cue in normalized for cue in EMOTION_CUES) + (.08 if "!" in normalized else 0))
    prompt_terms = {term for term in prompt.casefold().split() if len(term) > 3}
    prompt_relevance = .72 if not prompt_terms else min(.98, .35 + .13 * sum(term in normalized for term in prompt_terms))
    return CandidateSignals(
        hook=hook, coherence=max(0, coherence), value=value, emotion=emotion,
        visual_interest=.55, prompt_relevance=prompt_relevance,
        incomplete_thought_penalty=.55 if normalized.startswith(("e ", "mas ", "então ")) else 0,
    )

