from nixclip_processor.media import crop_geometry, piecewise_focus_expression, target_dimensions, timestamp, write_srt


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


def test_portrait_crop_tracks_horizontal_focus_and_stays_in_bounds() -> None:
    left = crop_geometry(1920, 1080, 9 / 16, focus_x=.2)
    right = crop_geometry(1920, 1080, 9 / 16, focus_x=.8)
    assert left[:2] == (606, 1080)
    assert right[:2] == (606, 1080)
    assert left[2] < right[2]
    assert left[2] >= 0
    assert right[2] + right[0] <= 1920


def test_tall_source_crop_tracks_vertical_focus() -> None:
    top = crop_geometry(1080, 1920, 1, focus_y=.2)
    bottom = crop_geometry(1080, 1920, 1, focus_y=.8)
    assert top[:2] == (1080, 1080)
    assert top[3] < bottom[3]


def test_piecewise_focus_expression_is_bounded_and_interpolated() -> None:
    expression = piecewise_focus_expression([(0, -20), (1, 500), (2, 1600)], 1314)
    assert expression.startswith("max(0\\,min(1314\\,")
    assert "if(lt(t\\,1.000)" in expression
    assert expression.endswith(")")


def test_render_does_not_upscale_a_720p_source_to_full_hd() -> None:
    assert target_dimensions(1280, 720, "9:16") == (720, 1280)
    assert target_dimensions(1920, 1080, "9:16") == (1080, 1920)
