from backend.infrastructure.vision.vision_prompt_builder import build_prompt_attempts


def test_build_prompt_attempts_creates_three_attempts():
    attempts = build_prompt_attempts(page_number=1, image_data_url="data:image/png;base64,abc")

    assert len(attempts) == 3
    assert attempts[0].force_json is True
    assert attempts[1].force_json is False
    assert attempts[2].force_json is False

    # Ensure messages include both system and user entries
    for attempt in attempts:
        assert attempt.messages[0]["role"] == "system"
        assert attempt.messages[1]["role"] == "user"
