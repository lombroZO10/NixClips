from nixclip_processor.media import timestamp, write_srt


def test_srt_timestamp_is_stable() -> None:
    assert timestamp(3_723_045) == "01:02:03,045"
    assert timestamp(-1) == "00:00:00,000"


def test_srt_splits_word_aligned_captions(tmp_path) -> None:
    words = [{"start": index * .4, "end": index * .4 + .35, "text": f" palavra{index}"} for index in range(7)]
    target = tmp_path / "captions.srt"
    write_srt(target, [{"start": 0, "end": 3, "text": "fallback", "words": words}], 0, 3_000)
    content = target.read_text(encoding="utf-8")
    assert "palavra0 palavra1 palavra2 palavra3 palavra4" in content
    assert "palavra5 palavra6" in content
    assert content.count("-->") == 2
