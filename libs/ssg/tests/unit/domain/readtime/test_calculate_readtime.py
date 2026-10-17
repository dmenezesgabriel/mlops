from ssg.domain.readtime import calculate_readtime_minutes


def test_calculate_readtime_minutes_rounds_up_to_next_minute() -> None:
    # Arrange
    html = "<p>" + " ".join(["word"] * 400) + "</p>"

    # Act & Assert
    assert calculate_readtime_minutes(html, words_per_minute=265) == 2


def test_calculate_readtime_minutes_includes_image_delays() -> None:
    # Arrange — 100 words ≈ 23s of reading; four images add the 12, 11, 10
    # and 9 second ramps, which crosses into a second minute.
    words = " ".join(["word"] * 100)
    html = (
        f"<p>{words}</p>"
        '<img src="one.png" />'
        '<img src="two.png" />'
        '<img src="three.png" />'
        '<img src="four.png" />'
    )

    # Act & Assert
    assert calculate_readtime_minutes(html, words_per_minute=265) == 2
    assert (
        calculate_readtime_minutes(f"<p>{words}</p>", words_per_minute=265)
        == 1
    )


def test_calculate_readtime_minutes_ignores_script_and_style_text() -> None:
    # Arrange
    words = " ".join(["word"] * 400)
    clean_html = f"<p>{words}</p>"
    noisy_html = (
        f"<script>{words}</script><style>{words}</style><p>{words}</p>"
    )

    # Act & Assert
    assert calculate_readtime_minutes(clean_html, words_per_minute=265) == (
        calculate_readtime_minutes(noisy_html, words_per_minute=265)
    )
