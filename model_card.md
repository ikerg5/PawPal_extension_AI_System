# Model Card — PawPal+ AI Care Advisor

This card documents the AI component added to PawPal+ for the Applied AI System
project: a retrieval-augmented advisor that suggests pet-care tasks using a local
knowledge base and the Gemini API (`gemini-flash-latest`).

## Limitations and Biases

- **Small, hand-curated knowledge base.** The advisor only knows what's in
  `knowledge_base/` — currently dog, cat, and rabbit care documents plus one
  general-safety document. Any species not covered (e.g. birds, reptiles) falls
  back to only the general-safety doc, and suggestions for uncommon breeds within
  a covered species are generic rather than breed-specific.
- **Keyword-based retrieval, not semantic search.** `advisor/retriever.py` scores
  documents by literal word overlap between the owner's free-text context and each
  doc's tags/text. A context phrase that's semantically related but lexically
  different (e.g. "doesn't like other animals" vs. "aggressive") may not surface
  the most relevant guidance. This was a deliberate scope tradeoff for a small,
  static knowledge base rather than standing up an embeddings pipeline.
- **Model output variance.** Gemini's suggestions are not deterministic — the same
  pet/context can produce different task titles, durations, or times across runs
  (observed directly in testing; see Testing Surprises below).
- **English-only, generic-owner assumptions.** The knowledge base and prompts
  assume an English-speaking owner with a typical home environment; no
  accessibility, multi-owner-household, or non-English-language handling exists.

## Potential Misuse and Mitigations

- **Risk: being trusted as veterinary/medical guidance.** The biggest misuse risk
  is an owner treating suggested tasks (or their rationale) as medical advice.
  Mitigation: the system prompt explicitly forbids medication names, dosages, and
  diagnostic claims, and `advisor/guardrails.py` independently re-checks every
  suggestion's text against a medical/dosage keyword blocklist — a suggestion is
  rejected and logged if it slips through the prompt instructions, and rejections
  are shown to the user with the reason, not silently dropped.
- **Risk: unattended task creation.** Suggestions are never written directly into
  a pet's real task list. Every suggestion requires an explicit "Accept into task
  list" click (human-in-the-loop checkpoint) — see `diagrams/architecture.mmd`.
- **Risk: prompt injection via owner free-text.** The "optional context" field is
  length-capped (`sanitize_context`, 300 chars) before reaching the prompt, and the
  system prompt constrains output to a strict JSON schema, limiting how much an
  adversarial input string could redirect model behavior into an unvalidated
  response shape (any response outside the schema fails `guardrails.py` validation
  and is rejected).

## Testing Surprises

- Gemini occasionally wraps its JSON response in a ```` ```json ```` markdown fence
  despite the system prompt explicitly saying not to — this was caught while
  building `test_advisor_service.py`'s malformed-output test and required adding
  `_strip_markdown_fence()` in `advisor_service.py` before parsing.
- The model consistently grounded every suggestion in the retrieved documents and
  cited real `source_doc_ids` rather than fabricating unlisted ones, across both
  live test runs (dog and cat) — better instruction-following than expected for a
  small, low-effort prompt.
- The guardrail's simple substring blocklist (`"mg"`, `"dose"`, etc.) is coarse
  enough that it could false-positive on an innocent suggestion that happens to
  contain one of those substrings (e.g. a task titled "Trim nails" is safe, but a
  hypothetical rationale mentioning a product name containing "mg" would be
  blocked). This tradeoff was accepted deliberately: over-blocking borderline-safe
  suggestions is a much smaller cost than under-blocking real medical content.

## AI Collaboration

This project was built with Claude (Anthropic) as a coding assistant, working
interactively through planning, implementation, and testing.

**One helpful suggestion:** while designing the Claude/Gemini response contract,
the assistant proactively added defensive markdown-fence stripping
(`_strip_markdown_fence` in `advisor_service.py`) before JSON parsing, anticipating
that LLMs commonly wrap structured output in code fences even when told not to.
This turned out to matter in practice — see Testing Surprises above.

**One flawed suggestion:** the initial implementation used Anthropic's Claude API
and, after switching providers to Gemini per the project owner's request, the
assistant picked `gemini-2.5-flash` as the model name based on general knowledge
without checking it against the actual API key's available models. The first live
test call failed with a 404 ("this model is no longer available to new users").
The fix required listing the account's actually-available models via the API and
switching to the `gemini-flash-latest` alias — a reminder that model names/aliases
drift over time and should be verified against a live API call rather than assumed,
especially for a fast-moving provider catalog.
