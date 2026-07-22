import json
from unittest.mock import patch

from advisor.advisor_service import get_suggestions
from advisor.llm_client import LLMClientError

_GOOD_RESPONSE = json.dumps([
    {
        "title": "Morning walk",
        "duration_minutes": 30,
        "priority": "high",
        "time": "08:00",
        "frequency": "daily",
        "rationale": "Dogs need daily exercise.",
        "source_doc_ids": ["dog_care"],
    }
])


@patch("advisor.advisor_service.call_llm", return_value=_GOOD_RESPONSE)
def test_well_formed_response_produces_accepted_suggestions(mock_call, tmp_path, monkeypatch):
    monkeypatch.setattr("advisor.advisor_service.LOG_PATH", tmp_path / "advisor_log.jsonl")

    response = get_suggestions(pet_name="Biscuit", species="dog", context="")

    assert response.error == ""
    assert len(response.accepted) == 1
    assert response.accepted[0]["title"] == "Morning walk"
    assert "dog_care" in response.retrieved_doc_ids


@patch("advisor.advisor_service.call_llm", return_value="```json\n" + _GOOD_RESPONSE + "\n```")
def test_markdown_fenced_response_is_parsed_correctly(mock_call, tmp_path, monkeypatch):
    monkeypatch.setattr("advisor.advisor_service.LOG_PATH", tmp_path / "advisor_log.jsonl")

    response = get_suggestions(pet_name="Biscuit", species="dog", context="")

    assert response.error == ""
    assert len(response.accepted) == 1


@patch("advisor.advisor_service.call_llm", return_value="not valid json { ]")
def test_malformed_model_output_does_not_crash(mock_call, tmp_path, monkeypatch):
    monkeypatch.setattr("advisor.advisor_service.LOG_PATH", tmp_path / "advisor_log.jsonl")

    response = get_suggestions(pet_name="Biscuit", species="dog", context="")

    assert response.accepted == []
    assert response.error != ""


@patch("advisor.advisor_service.call_llm", side_effect=LLMClientError("API unavailable"))
def test_llm_api_error_is_handled_gracefully(mock_call, tmp_path, monkeypatch):
    monkeypatch.setattr("advisor.advisor_service.LOG_PATH", tmp_path / "advisor_log.jsonl")

    response = get_suggestions(pet_name="Biscuit", species="dog", context="")

    assert response.accepted == []
    assert "API unavailable" in response.error


@patch("advisor.advisor_service.call_llm", return_value=json.dumps([
    {"title": "Give medication", "duration_minutes": 5, "priority": "high",
     "time": "", "frequency": "once", "rationale": "5mg dosage as needed", "source_doc_ids": []}
]))
def test_unsafe_suggestion_is_rejected_not_shown_as_accepted(mock_call, tmp_path, monkeypatch):
    monkeypatch.setattr("advisor.advisor_service.LOG_PATH", tmp_path / "advisor_log.jsonl")

    response = get_suggestions(pet_name="Biscuit", species="dog", context="")

    assert response.accepted == []
    assert len(response.rejected) == 1
