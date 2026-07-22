"""Input/output guardrails for the AI advisor: keeps unsafe or malformed content
from ever becoming a real Task, and keeps values inside sane ranges.
"""

from dataclasses import dataclass, field
from typing import List

MAX_CONTEXT_CHARS = 300
MAX_DURATION_MINUTES = 240
MIN_DURATION_MINUTES = 1
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_FREQUENCIES = {"once", "daily", "weekly"}

# Keywords that indicate the suggestion has drifted into medical-advice territory.
# Deliberately broad/simple (substring match) — false positives are acceptable
# here since the cost of blocking a borderline-safe suggestion is much lower than
# the cost of letting medical advice through.
UNSAFE_KEYWORDS = [
    "mg", "milligram", "dose", "dosage", "diagnos", "prescri",
    "antibiotic", "medication for", "treat the", "cure",
]


@dataclass
class GuardrailResult:
    """The verdict for one suggestion: whether it's safe to show, plus why."""

    accepted: bool
    reason: str = ""
    suggestion: dict = field(default_factory=dict)


def sanitize_context(context: str) -> str:
    """Trim owner-provided free text to a safe max length before it reaches the prompt."""
    return (context or "").strip()[:MAX_CONTEXT_CHARS]


def _contains_unsafe_content(suggestion: dict) -> str | None:
    text = f"{suggestion.get('title', '')} {suggestion.get('rationale', '')}".lower()
    for keyword in UNSAFE_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def validate_suggestion(raw: dict) -> GuardrailResult:
    """Check one parsed suggestion dict: reject unsafe content, clamp/validate ranges."""
    if not isinstance(raw, dict) or "title" not in raw:
        return GuardrailResult(accepted=False, reason="Malformed suggestion (missing title).")

    unsafe_hit = _contains_unsafe_content(raw)
    if unsafe_hit:
        return GuardrailResult(
            accepted=False,
            reason=f"Blocked: contains medical/dosage-like content ('{unsafe_hit}').",
        )

    try:
        duration = int(raw.get("duration_minutes", 0))
    except (TypeError, ValueError):
        return GuardrailResult(accepted=False, reason="Malformed duration_minutes.")
    duration = max(MIN_DURATION_MINUTES, min(MAX_DURATION_MINUTES, duration))

    priority = str(raw.get("priority", "")).lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    frequency = str(raw.get("frequency", "")).lower()
    if frequency not in VALID_FREQUENCIES:
        frequency = "once"

    cleaned = {
        "title": str(raw.get("title", "")).strip()[:80],
        "duration_minutes": duration,
        "priority": priority,
        "time": str(raw.get("time", "") or ""),
        "frequency": frequency,
        "rationale": str(raw.get("rationale", "")).strip()[:300],
        "source_doc_ids": raw.get("source_doc_ids", []) if isinstance(raw.get("source_doc_ids"), list) else [],
    }
    return GuardrailResult(accepted=True, suggestion=cleaned)


def validate_suggestions(raw_list: List[dict]) -> List[GuardrailResult]:
    """Run validate_suggestion over every item in a parsed suggestion list."""
    return [validate_suggestion(item) for item in raw_list]
