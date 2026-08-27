from nixclip_processor.curation import build_candidates, curate_transcript
from nixclip_processor.models import Preferences


def segment(start: float, end: float, text: str, confidence: float = .94) -> dict:
    words = text.split()
    step = (end - start) / max(len(words), 1)
    return {
        "start": start, "end": end, "text": text,
        "words": [
            {"start": start + index * step, "end": start + (index + 1) * step, "text": f" {word}", "probability": confidence}
            for index, word in enumerate(words)
        ],
    }


def sample_transcript() -> list[dict]:
    return [
        segment(0, 8, "Você sabe qual é o problema que impede quase todo mundo de conseguir um resultado melhor?"),
        segment(8.7, 18, "A maioria tenta produzir mais, mas ignora completamente a clareza da mensagem principal."),
        segment(18.4, 29, "O primeiro passo é escolher uma única ideia e explicar por que ela realmente importa."),
        segment(29.8, 41, "Quando você faz isso, o conteúdo fica simples, memorável e muito mais fácil de compartilhar."),
        segment(70, 80, "E então a gente continua falando sem apresentar uma conclusão clara para essa parte"),
        segment(80.02, 92, "porque ainda faltava explicar outra coisa que dependia do assunto anterior"),
    ]


def test_candidates_include_score_evidence_and_pause_aligned_boundaries() -> None:
    candidates = build_candidates(sample_transcript(), Preferences(clip_length="medium", clip_count=3))
    assert candidates
    best = max(candidates, key=lambda candidate: candidate.selection_score).clip
    assert best.score_breakdown is not None
    assert best.reasons
    assert best.transcript_excerpt
    assert best.start_ms in {0, 8_480, 18_180, 29_580, 69_780, 80_012}
    assert best.end_ms > best.start_ms


def test_curator_rejects_near_duplicate_windows() -> None:
    clips = curate_transcript(sample_transcript(), Preferences(clip_length="medium", clip_count=5))
    assert 1 <= len(clips) < 5
    for index, clip in enumerate(clips):
        for other in clips[index + 1:]:
            overlap = max(0, min(clip.end_ms, other.end_ms) - max(clip.start_ms, other.start_ms))
            shorter = min(clip.end_ms - clip.start_ms, other.end_ms - other.start_ms)
            assert overlap / shorter <= .34
