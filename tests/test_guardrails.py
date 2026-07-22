from advisor.guardrails import MAX_DURATION_MINUTES, sanitize_context, validate_suggestion


def _base_suggestion(**overrides):
    suggestion = {
        "title": "Morning walk",
        "duration_minutes": 30,
        "priority": "high",
        "time": "08:00",
        "frequency": "daily",
        "rationale": "Dogs need daily exercise.",
        "source_doc_ids": ["dog_care"],
    }
    suggestion.update(overrides)
    return suggestion


def test_clean_suggestion_is_accepted():
    result = validate_suggestion(_base_suggestion())

    assert result.accepted is True
    assert result.suggestion["title"] == "Morning walk"


def test_dosage_keyword_is_rejected():
    unsafe = _base_suggestion(rationale="Give 5mg of medication for this condition.")

    result = validate_suggestion(unsafe)

    assert result.accepted is False
    assert "medical" in result.reason.lower() or "dosage" in result.reason.lower()


def test_missing_title_is_rejected():
    result = validate_suggestion({"duration_minutes": 10})

    assert result.accepted is False


def test_out_of_range_duration_is_clamped_not_rejected():
    result = validate_suggestion(_base_suggestion(duration_minutes=9999))

    assert result.accepted is True
    assert result.suggestion["duration_minutes"] == MAX_DURATION_MINUTES


def test_invalid_priority_falls_back_to_medium():
    result = validate_suggestion(_base_suggestion(priority="urgent!!"))

    assert result.accepted is True
    assert result.suggestion["priority"] == "medium"


def test_sanitize_context_truncates_long_input():
    long_text = "a" * 1000

    cleaned = sanitize_context(long_text)

    assert len(cleaned) <= 300
