"""Reproducible CLI demo of the AI Care Advisor pipeline (retrieval -> Gemini -> guardrails).

Run with GEMINI_API_KEY set to see live suggestions for two real pets, plus a
guardrail demo using a deliberately unsafe synthetic model response (patched in,
since real models can't be reliably forced to violate their own instructions).
"""

from unittest.mock import patch

from advisor.advisor_service import get_suggestions


def _print_response(label: str, response) -> None:
    print(f"\n=== {label} ===")
    print(f"Retrieved docs: {response.retrieved_doc_ids}")
    if response.error:
        print(f"ERROR: {response.error}")
        return
    print(f"Accepted suggestions ({len(response.accepted)}):")
    for s in response.accepted:
        print(f"  - {s['title']} | {s['duration_minutes']} min | {s['priority']} priority "
              f"| {s['frequency']} | source: {s['source_doc_ids']}")
        print(f"    rationale: {s['rationale']}")
    if response.rejected:
        print(f"Rejected by guardrails ({len(response.rejected)}):")
        for r in response.rejected:
            print(f"  - BLOCKED: {r.reason}")


def main():
    _print_response(
        "Live Gemini call: dog, no extra context",
        get_suggestions(pet_name="Biscuit", species="dog", context=""),
    )

    _print_response(
        "Live Gemini call: cat, with owner context",
        get_suggestions(pet_name="Mochi", species="cat", context="indoor cat, low energy"),
    )

    unsafe_response = (
        '[{"title": "Give medication", "duration_minutes": 5, "priority": "high", '
        '"time": "", "frequency": "once", "rationale": "Administer 5mg dosage as needed", '
        '"source_doc_ids": []}]'
    )
    with patch("advisor.advisor_service.call_llm", return_value=unsafe_response):
        _print_response(
            "Guardrail demo: synthetic unsafe model response (patched, not live)",
            get_suggestions(pet_name="Biscuit", species="dog", context=""),
        )


if __name__ == "__main__":
    main()
