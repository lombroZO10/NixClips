from nixclip_processor.scoring import CandidateSignals, explain_score, lexical_signals, score_candidate


def test_score_is_clamped_to_product_scale() -> None:
    assert score_candidate(CandidateSignals(2, 2, 2, 2, 2, 2)) == 99
    assert score_candidate(CandidateSignals(0, 0, 0, 0, 0, 0, bad_boundary_penalty=2)) == 0


def test_complete_value_statement_scores_above_incomplete_fragment() -> None:
    complete = lexical_signals("O problema é este: você precisa escolher melhor porque isso muda o resultado.", 38)
    fragment = lexical_signals("E então a gente foi fazendo", 9)
    assert score_candidate(complete) > score_candidate(fragment)


def test_score_explanation_surfaces_strongest_dimensions() -> None:
    signals = lexical_signals(
        "Você sabe qual é o problema? O erro mais importante muda o resultado porque existe uma solução.",
        34, pause_before=.8, pause_after=.9, average_confidence=.94,
    )
    details = explain_score(signals)
    assert 0 <= details.score <= 99
    assert details.dimensions["coherence"] >= 70
    assert 1 <= len(details.reasons) <= 3
