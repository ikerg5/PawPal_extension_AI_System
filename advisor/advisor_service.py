"""Orchestrates one advisor request: retrieve -> prompt -> call the LLM -> guardrail ->
log -> return validated suggestions ready to become real Task objects.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from advisor.llm_client import LLMClientError, call_llm
from advisor.guardrails import GuardrailResult, sanitize_context, validate_suggestions
from advisor.knowledge_base import load_knowledge_base
from advisor.prompt import SYSTEM_PROMPT, build_user_prompt
from advisor.retriever import retrieve

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "advisor_log.jsonl"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_markdown_fence(text: str) -> str:
    """Some models wrap JSON in ```json fences despite instructions not to; strip them."""
    return _FENCE_RE.sub("", text).strip()


@dataclass
class AdvisorResponse:
    """What the UI needs: accepted suggestions, rejected ones (with reasons), and any hard error."""

    accepted: List[dict]
    rejected: List[GuardrailResult]
    retrieved_doc_ids: List[str]
    error: str = ""


def _log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_suggestions(pet_name: str, species: str, context: str = "") -> AdvisorResponse:
    """Run the full retrieve -> prompt -> LLM -> guardrail pipeline for one pet."""
    context = sanitize_context(context)
    docs = load_knowledge_base()
    retrieved = retrieve(species=species, context=context, docs=docs)
    doc_ids = [d.doc_id for d in retrieved]

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        raw_text = call_llm(SYSTEM_PROMPT, build_user_prompt(pet_name, species, context, retrieved))
    except LLMClientError as exc:
        _log({
            "timestamp": timestamp, "pet_name": pet_name, "species": species,
            "retrieved_doc_ids": doc_ids, "error": str(exc),
        })
        return AdvisorResponse(accepted=[], rejected=[], retrieved_doc_ids=doc_ids, error=str(exc))

    try:
        parsed = json.loads(_strip_markdown_fence(raw_text))
        if not isinstance(parsed, list):
            raise ValueError("Model response was not a JSON array.")
    except (json.JSONDecodeError, ValueError) as exc:
        _log({
            "timestamp": timestamp, "pet_name": pet_name, "species": species,
            "retrieved_doc_ids": doc_ids, "raw_output": raw_text, "error": f"parse failure: {exc}",
        })
        return AdvisorResponse(
            accepted=[], rejected=[], retrieved_doc_ids=doc_ids,
            error="The AI response could not be parsed. Please try again.",
        )

    results = validate_suggestions(parsed)
    accepted = [r.suggestion for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]

    _log({
        "timestamp": timestamp,
        "pet_name": pet_name,
        "species": species,
        "retrieved_doc_ids": doc_ids,
        "raw_output": raw_text,
        "accepted_count": len(accepted),
        "rejected": [asdict(r) for r in rejected],
    })

    return AdvisorResponse(accepted=accepted, rejected=rejected, retrieved_doc_ids=doc_ids)
