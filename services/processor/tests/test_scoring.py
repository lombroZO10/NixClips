from nixclip_processor.scoring import CandidateSignals, lexical_signals, score_candidate


def test_score_is_clamped_to_product_scale() -> None:
    assert score_candidate(CandidateSignals(2, 2, 2, 2, 2, 2)) == 99
    assert score_candidate(CandidateSignals(0, 0, 0, 0, 0, 0, bad_boundary_penalty=2)) == 0


def test_complete_value_statement_scores_above_incomplete_fragment() -> None:
    complete = lexical_signals("O problema é este: você precisa escolher melhor porque isso muda o resultado.", 38)
    fragment = lexical_signals("E então a gente foi fazendo", 9)
    assert score_candidate(complete) > score_candidate(fragment)

