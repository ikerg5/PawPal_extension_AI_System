# PawPal+ Applied AI System — RAG Pet-Care Advisor

## Base project

This project extends **PawPal+ (Module 2 Project)**, a Streamlit pet-care task
scheduler. The original project let a pet owner track care tasks (walks, feeding,
grooming, etc.) across multiple pets, generate a time-boxed daily schedule ordered
by priority, detect same-time scheduling conflicts, and auto-create the next
occurrence of recurring tasks. It was entirely deterministic, rule-based Python —
no AI/LLM involved.

## What's new: AI Care Advisor (RAG)

This extension adds a **retrieval-augmented AI advisor**. Given a pet's species and
optional owner context, it retrieves grounded guidance from a small local knowledge
base (`knowledge_base/*.md`), asks Gemini to propose concrete care tasks citing
which document(s) informed each one, runs every suggestion through a guardrail
layer that blocks medical/dosage-like content, and — only after the owner clicks
"Accept" on a specific suggestion — turns it into a real `Task` object via the
existing `Pet.add_task()`. Accepted tasks flow through the original, unmodified
`Scheduler` (priority sort, conflict detection, time-budget fitting) exactly like
any manually entered task.

### Architecture Overview

See [`diagrams/architecture.mmd`](diagrams/architecture.mmd) for the full Mermaid
diagram. In short: **Owner input → Retriever (queries `knowledge_base/`) → Prompt
builder → Gemini API → Guardrail/validator → human accept/reject checkpoint →
existing `Pet.add_task()` / `Scheduler` → `DailyPlan`.** Every advisor call —
accepted, rejected, or errored — is logged to `logs/advisor_log.jsonl`.

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Get a free Gemini API key from Google AI Studio, then either:
export GEMINI_API_KEY="your-key-here"  # Windows: set GEMINI_API_KEY=your-key-here
# ...or create a local .env file (gitignored, never committed) containing:
#   GEMINI_API_KEY=your-key-here
# app.py and demo_advisor.py both load .env automatically via python-dotenv.

streamlit run app.py
```

The advisor UI appears as a new "🤖 AI Care Advisor" section in the app, below
manual task entry. If `GEMINI_API_KEY` is not set, the section still renders — it
shows a friendly error instead of crashing (see Guardrails below).

### Sample Interactions

These are real, unedited outputs from a live run against the Gemini API (captured
via `python demo_advisor.py`, reproducible by anyone with a `GEMINI_API_KEY` set —
see [`demo_advisor.py`](demo_advisor.py)).

**1. Dog, no extra context:**

```
=== Live Gemini call: dog, no extra context ===
Retrieved docs: ['dog_care', 'general_safety']
Accepted suggestions (5):
  - Morning Walk | 30 min | high priority | daily | source: ['dog_care', 'general_safety']
    rationale: A brisk morning walk provides essential daily exercise and handles bathroom needs for Biscuit.
  - Morning Feeding | 10 min | high priority | daily | source: ['dog_care', 'general_safety']
    rationale: Adult dogs need to be fed twice a day as missing meals directly impacts their health.
  - Evening Feeding | 10 min | high priority | daily | source: ['dog_care', 'general_safety']
    rationale: Providing a second daily meal ensures proper health and consistent nutrition.
  - Daily Play or Training Session | 15 min | medium priority | daily | source: ['dog_care', 'general_safety']
    rationale: Short daily play or training sessions provide mental enrichment and prevent boredom-related behavior issues.
  - Coat Brushing | 15 min | low priority | weekly | source: ['dog_care', 'general_safety']
    rationale: Weekly brushing serves as basic coat maintenance and is a low-priority maintenance task.
```

**2. Cat, with owner context ("indoor cat, low energy"):**

```
=== Live Gemini call: cat, with owner context ===
Retrieved docs: ['cat_care', 'general_safety']
Accepted suggestions (4):
  - Feed Mochi | 10 min | high priority | daily | source: ['cat_care', 'general_safety']
    rationale: Scheduled daily feeding provides proper intake monitoring and essential nutrition for daily health.
  - Scoop Litter Box | 10 min | high priority | daily | source: ['cat_care', 'general_safety']
    rationale: Scooping daily ensures the box remains usable and allows observation of changes in litter habits.
  - Interactive Play Session | 15 min | medium priority | daily | source: ['cat_care']
    rationale: Daily interactive play satisfies a cat's predatory instinct and helps prevent stress-related behavior issues.
  - Brush Coat | 10 min | low priority | weekly | source: ['cat_care', 'general_safety']
    rationale: Weekly brushing serves as a low-priority routine task to assist with self-grooming and coat maintenance.
```

**3. Guardrail demo — synthetic unsafe model response (patched in, since a
correctly-instructed model won't reliably produce unsafe output on demand; this
demonstrates the guardrail actually catching it rather than trusting the model):**

```
=== Guardrail demo: synthetic unsafe model response (patched, not live) ===
Retrieved docs: ['dog_care', 'general_safety']
Accepted suggestions (0):
Rejected by guardrails (1):
  - BLOCKED: Blocked: contains medical/dosage-like content ('mg').
```

Corresponding log entries (`logs/advisor_log.jsonl`, pretty-printed excerpt):

```json
{
  "timestamp": "2026-07-22T02:01:52.520536+00:00",
  "pet_name": "Biscuit",
  "species": "dog",
  "retrieved_doc_ids": ["dog_care", "general_safety"],
  "raw_output": "[{\"title\": \"Give medication\", ... \"rationale\": \"Administer 5mg dosage as needed\", ...}]",
  "accepted_count": 0,
  "rejected": [
    {"accepted": false, "reason": "Blocked: contains medical/dosage-like content ('mg').", "suggestion": {}}
  ]
}
```

### Design Decisions

- **Keyword/tag retrieval instead of embeddings.** The knowledge base is four
  small, static markdown files. A vector database or embedding model would add
  setup cost and a new dependency with no real benefit at this scale — simple
  species-match plus keyword-overlap scoring (`advisor/retriever.py`) is
  transparent, fast, and easy to unit test.
- **Guardrail is a second, independent check — not just a prompt instruction.**
  The system prompt tells the model never to give medical/dosage advice, but
  `advisor/guardrails.py` re-validates every suggestion's text against a keyword
  blocklist regardless of what the prompt says. Trusting only the prompt would mean
  one model slip-up reaches the user; the guardrail is the actual enforcement point.
- **Suggestions never auto-populate the task list.** Every suggestion requires an
  explicit per-item "Accept" click. This keeps a human in the loop for every piece
  of AI-generated content that becomes real application state.
- **Gemini over Claude.** The project initially used the Anthropic API but was
  switched to Google's Gemini API (`gemini-flash-latest`) to use a free-tier key
  instead of a paid one — see `model_card.md` for the model-name issue this
  surfaced during testing.

### Testing Summary

```
$ python -m pytest -v
============================= test session starts ==============================
collected 24 items

tests/test_advisor_service.py::test_well_formed_response_produces_accepted_suggestions PASSED [  4%]
tests/test_advisor_service.py::test_markdown_fenced_response_is_parsed_correctly PASSED [  8%]
tests/test_advisor_service.py::test_malformed_model_output_does_not_crash PASSED [ 12%]
tests/test_advisor_service.py::test_llm_api_error_is_handled_gracefully PASSED [ 16%]
tests/test_advisor_service.py::test_unsafe_suggestion_is_rejected_not_shown_as_accepted PASSED [ 20%]
tests/test_guardrails.py::test_clean_suggestion_is_accepted PASSED       [ 25%]
tests/test_guardrails.py::test_dosage_keyword_is_rejected PASSED         [ 29%]
tests/test_guardrails.py::test_missing_title_is_rejected PASSED          [ 33%]
tests/test_guardrails.py::test_out_of_range_duration_is_clamped_not_rejected PASSED [ 37%]
tests/test_guardrails.py::test_invalid_priority_falls_back_to_medium PASSED [ 41%]
tests/test_guardrails.py::test_sanitize_context_truncates_long_input PASSED [ 45%]
tests/test_pawpal.py (10 original scheduler tests) ....................... PASSED [ 45%-87%]
tests/test_retriever.py::test_retrieve_returns_species_specific_doc_plus_general PASSED [ 91%]
tests/test_retriever.py::test_retrieve_unknown_species_returns_only_general_docs PASSED [ 95%]
tests/test_retriever.py::test_retrieve_empty_docs_list_returns_empty PASSED [100%]

============================== 24 passed in 0.03s ===============================
```

**24 of 24 tests passed** (10 original scheduler tests + 14 new advisor tests: 5
service-level, 6 guardrail, 3 retriever). All Gemini calls are mocked in the
automated suite (`unittest.mock.patch`) so tests run offline and deterministically;
the live-model behavior is separately demonstrated above via `demo_advisor.py`.
The guardrail correctly caught the one synthetic unsafe case it was tested against
(dosage keyword), and both live-model runs produced suggestions grounded in and
citing the correct retrieved documents with no unsafe content — 2/2 live runs
usable without edits.

**Reflection:** the graded responsible-AI reflection — collaboration with AI, one
helpful and one flawed AI suggestion, and system limitations — is documented in
[`model_card.md`](model_card.md), not here.

---

## PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## ✨ Features

- **Multi-pet management** — one owner can track any number of pets, each with its own task list
- **Priority-based scheduling** — `Scheduler.generate_plan()` sorts tasks high → medium → low priority and greedily fits as many as possible into the owner's available minutes
- **Sorting by time** — `Scheduler.sort_by_time()` orders tasks chronologically by their `"HH:MM"` scheduled time
- **Filtering** — `Scheduler.filter_by_pet()` and `filter_by_status()` narrow the task list down to one pet or one completion state
- **Conflict warnings** — `Scheduler.detect_conflicts()` flags any tasks scheduled at the same time (even across different pets) and surfaces a warning instead of silently double-booking
- **Daily recurrence** — completing a `"daily"` or `"weekly"` task automatically creates the next occurrence, due exactly 1 day or 1 week later, via `Task.next_occurrence()` and `Pet.complete_task()`

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
$ python main.py
Today's Schedule for Jordan
---------------------------
  [ ] [Biscuit] Morning walk (30 min, high priority)
  [ ] [Biscuit] Feeding (10 min, high priority)
  [ ] [Mochi] Litter box cleaning (10 min, medium priority)

Total time used: 50 minutes
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
python -m pytest

# Run with coverage:
pytest --cov
```

The suite (`tests/test_pawpal.py`) covers:
- **Basic behaviors**: marking a task complete, adding a task increases a pet's task count
- **Sorting**: `sort_by_time()` returns chronological order, and handles an empty task list
- **Recurrence**: completing a `"daily"` task auto-creates the next day's occurrence; completing a `"once"` task creates nothing
- **Conflict detection**: two tasks at the same time are flagged; tasks at different times are not
- **Filtering edge cases**: filtering by a pet/status with no matches returns an empty list rather than erroring
- **Empty state**: generating a plan for an owner with no pets returns an empty, zero-duration plan

Sample test output:

```
$ python -m pytest -v
============================= test session starts ==============================
collected 10 items

tests/test_pawpal.py::test_mark_complete_changes_task_status PASSED      [ 10%]
tests/test_pawpal.py::test_adding_task_increases_pet_task_count PASSED   [ 20%]
tests/test_pawpal.py::test_sort_by_time_returns_chronological_order PASSED [ 30%]
tests/test_pawpal.py::test_sort_by_time_on_empty_list_returns_empty_list PASSED [ 40%]
tests/test_pawpal.py::test_completing_daily_task_creates_next_day_occurrence PASSED [ 50%]
tests/test_pawpal.py::test_completing_a_one_time_task_creates_no_next_occurrence PASSED [ 60%]
tests/test_pawpal.py::test_detect_conflicts_flags_tasks_at_the_same_time PASSED [ 70%]
tests/test_pawpal.py::test_detect_conflicts_finds_none_when_times_differ PASSED [ 80%]
tests/test_pawpal.py::test_filter_by_pet_with_no_matches_returns_empty_list PASSED [ 90%]
tests/test_pawpal.py::test_generate_plan_for_owner_with_no_pets_returns_empty_plan PASSED [100%]

============================== 10 passed in 0.02s ===============================
```

**Confidence Level:** ⭐⭐⭐⭐☆ (4/5) — core sorting, filtering, recurrence, and exact-time conflict detection are all verified. The main known gap (see `reflection.md` 2b) is that conflict detection only catches exact time matches, not overlapping durations, so that's the main scenario not yet covered by tests.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sort by priority | `Scheduler.sort_by_priority()` | Orders tasks high → medium → low |
| Sort by time | `Scheduler.sort_by_time()` | Orders tasks by their `"HH:MM"` scheduled time; untimed tasks sort last |
| Filtering by pet | `Scheduler.filter_by_pet()` | Returns only the tasks belonging to a given pet |
| Filtering by status | `Scheduler.filter_by_status()` | Returns only tasks matching a completion status |
| Time-budget filtering | `Scheduler.filter_by_time()` | Greedily keeps tasks that fit within the owner's available minutes |
| Conflict handling | `Scheduler.detect_conflicts()` | Flags tasks that share the same scheduled time and returns warning strings (does not crash); only checks exact time matches, not overlapping durations — see `reflection.md` section 2b |
| Recurring tasks | `Task.next_occurrence()`, `Pet.complete_task()` | Completing a `"daily"`/`"weekly"` task automatically creates its next occurrence, with `due_date` advanced via `timedelta` |

## 📸 Demo Walkthrough

### UI features and available actions

The Streamlit app (`app.py`) lets a user:

- Set their **owner name** and **available minutes** for the day
- **Add pets** (name + species), shown in a running table with each pet's task count
- **Add tasks** to a specific pet, including title, duration, priority, an optional scheduled time, and a frequency (`once`/`daily`/`weekly`)
- View the **current task list sorted chronologically by time**
- See a **warning banner** immediately if two tasks land at the same time, before even generating a schedule
- **Check off tasks as done** — completing a recurring task automatically creates and reports its next occurrence
- Click **"Generate schedule"** to build and display the day's time-boxed plan

### Example workflow

1. Enter the owner's name and available minutes (e.g., "Jordan", 60 minutes).
2. Add two pets: "Biscuit" (dog) and "Mochi" (cat).
3. Add tasks for each pet with different times and priorities — including one deliberate clash, e.g. both pets with a task at 08:00.
4. Notice the conflict warning appear above the task list as soon as the clash exists.
5. Check off a daily task as "Done" and see a confirmation that tomorrow's occurrence was created automatically.
6. Click "Generate schedule" to see the final plan: highest-priority tasks first, cut off once the available minutes run out.

### Key Scheduler behaviors shown

- **Sorting** — tasks display in time order (`Scheduler.sort_by_time()`) and get prioritized high → low when building the plan (`Scheduler.sort_by_priority()`)
- **Conflict warnings** — `Scheduler.detect_conflicts()` catches the same-time clash and surfaces it as a banner
- **Recurrence** — `Pet.complete_task()` auto-spawns tomorrow's/next week's task when a recurring task is checked off

### Sample CLI output (`python main.py`)

```
All tasks sorted by time:
  08:00  [ ] [Biscuit] Morning walk (30 min, high priority)
  08:00  [ ] [Mochi] Feeding (10 min, high priority)
  09:00  [ ] [Mochi] Litter box cleaning (10 min, medium priority)
  12:30  [ ] [Biscuit] Brushing (15 min, low priority)
  17:00  [ ] [Mochi] Playtime (20 min, medium priority)
  18:00  [ ] [Biscuit] Feeding (10 min, high priority)

Biscuit's tasks only (filter_by_pet):
  [ ] [Biscuit] Feeding (10 min, high priority)
  [ ] [Biscuit] Morning walk (30 min, high priority)
  [ ] [Biscuit] Brushing (15 min, low priority)

Incomplete tasks only (filter_by_status):
  [ ] [Biscuit] Feeding (10 min, high priority)
  [ ] [Biscuit] Morning walk (30 min, high priority)
  [ ] [Biscuit] Brushing (15 min, low priority)
  [ ] [Mochi] Playtime (20 min, medium priority)
  [ ] [Mochi] Litter box cleaning (10 min, medium priority)
  [ ] [Mochi] Feeding (10 min, high priority)

Conflict check:
  WARNING: Conflict at 08:00 — Biscuit: Morning walk, Mochi: Feeding

Today's Schedule for Jordan
---------------------------
  [ ] [Biscuit] Feeding (10 min, high priority)
  [ ] [Biscuit] Morning walk (30 min, high priority)
  [ ] [Mochi] Feeding (10 min, high priority)
  [ ] [Mochi] Litter box cleaning (10 min, medium priority)

Total time used: 60 minutes

Completing Biscuit's daily 'Morning walk'...
  Completed: [x] [Biscuit] Morning walk (30 min, high priority) (was due 2026-07-07)
  Next occurrence auto-created: [ ] [Biscuit] Morning walk (30 min, high priority) (due 2026-07-08)
  Biscuit now has 4 tasks
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
