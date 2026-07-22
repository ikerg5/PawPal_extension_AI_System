import streamlit as st

from advisor.advisor_service import get_suggestions
from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to **PawPal+**, a pet care planning assistant. Set up your profile and pets,
add care tasks, then generate a daily schedule that fits your available time.
"""
)

# --- Session "memory" -------------------------------------------------------
# Streamlit reruns this whole script on every interaction, so we keep the
# Owner (and everything hanging off it) in st.session_state instead of
# recreating it — otherwise it would be wiped on every click.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_minutes=60)

owner: Owner = st.session_state.owner

st.divider()

# --- Owner setup -------------------------------------------------------------
st.subheader("Owner")
col1, col2 = st.columns(2)
with col1:
    owner.name = st.text_input("Owner name", value=owner.name)
with col2:
    owner.available_minutes = st.number_input(
        "Available minutes today", min_value=1, max_value=600, value=owner.available_minutes
    )

st.divider()

# --- Add a pet ---------------------------------------------------------------
st.subheader("Pets")

with st.form("add_pet_form", clear_on_submit=True):
    st.caption("Add a pet")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        new_pet_name = st.text_input("Pet name", value="")
    with pcol2:
        new_species = st.selectbox("Species", ["dog", "cat", "rabbit", "other"])

    if st.form_submit_button("Add pet"):
        if new_pet_name.strip():
            owner.add_pet(Pet(name=new_pet_name.strip(), species=new_species))
        else:
            st.warning("Enter a pet name before adding.")

if owner.pets:
    st.table(
        [{"name": pet.name, "species": pet.species, "tasks": pet.task_count} for pet in owner.pets]
    )
else:
    st.info("No pets yet. Add one above.")

st.divider()

# --- Add a task ---------------------------------------------------------------
st.subheader("Tasks")

if not owner.pets:
    st.info("Add a pet first before adding tasks.")
else:
    with st.form("add_task_form", clear_on_submit=True):
        st.caption("Add a care task for one of your pets")
        pet_names = [pet.name for pet in owner.pets]
        selected_pet_name = st.selectbox("Pet", pet_names)

        tcol1, tcol2, tcol3 = st.columns(3)
        with tcol1:
            task_title = st.text_input("Task title", value="Morning walk")
        with tcol2:
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        with tcol3:
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

        tcol4, tcol5 = st.columns(2)
        with tcol4:
            task_time = st.time_input("Scheduled time", value=None)
        with tcol5:
            frequency = st.selectbox("Frequency", ["once", "daily", "weekly"])

        if st.form_submit_button("Add task"):
            selected_pet = next(pet for pet in owner.pets if pet.name == selected_pet_name)
            selected_pet.add_task(
                Task(
                    title=task_title,
                    duration_minutes=int(duration),
                    priority=priority,
                    time=task_time.strftime("%H:%M") if task_time else "",
                    frequency=frequency,
                )
            )

    scheduler = Scheduler(owner)
    all_tasks = owner.get_all_tasks()

    if all_tasks:
        # Show tasks in chronological order so the owner can scan the day at a glance.
        sorted_tasks = scheduler.sort_by_time(all_tasks)

        conflicts = scheduler.detect_conflicts(all_tasks)
        for warning in conflicts:
            st.warning(f"⚠️ {warning} — these tasks overlap, consider rescheduling one.")

        st.write("Current tasks (sorted by time):")

        for task in sorted_tasks:
            tcol, ccol = st.columns([5, 1])
            with tcol:
                st.write(
                    f"**{task.time or '--:--'}** — [{task.pet_name}] {task.title} "
                    f"({task.duration_minutes} min, {task.priority} priority"
                    f"{', ' + task.frequency if task.frequency != 'once' else ''})"
                )
            with ccol:
                already_complete = task.is_complete
                if st.checkbox("Done", value=already_complete, key=f"complete-{id(task)}") and not already_complete:
                    owning_pet = next(pet for pet in owner.pets if pet.name == task.pet_name)
                    next_task = owning_pet.complete_task(task)
                    if next_task is not None:
                        st.success(
                            f"'{task.title}' completed — next {task.frequency} occurrence "
                            f"scheduled for {next_task.due_date}."
                        )
                    st.rerun()
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

# --- AI care advisor (RAG) ----------------------------------------------------
st.subheader("🤖 AI Care Advisor")
st.caption(
    "Retrieves grounded care guidance from a local knowledge base and asks Gemini to "
    "suggest tasks for a chosen pet. Suggestions are validated by a guardrail layer "
    "before you can add them to the real task list — nothing is added automatically."
)

if not owner.pets:
    st.info("Add a pet first before requesting AI suggestions.")
else:
    advisor_pet_name = st.selectbox("Pet to get suggestions for", [pet.name for pet in owner.pets], key="advisor_pet")
    advisor_context = st.text_input(
        "Optional context (e.g. \"senior dog, low energy\")", value="", key="advisor_context"
    )

    if st.button("Suggest tasks with AI"):
        advisor_pet = next(pet for pet in owner.pets if pet.name == advisor_pet_name)
        with st.spinner("Retrieving care guidance and asking Gemini..."):
            result = get_suggestions(
                pet_name=advisor_pet.name, species=advisor_pet.species, context=advisor_context
            )
        st.session_state.advisor_result = result
        st.session_state.advisor_result_pet = advisor_pet.name

    result = st.session_state.get("advisor_result")
    result_pet_name = st.session_state.get("advisor_result_pet")

    if result is not None and result_pet_name == advisor_pet_name:
        if result.error:
            st.error(f"AI advisor unavailable: {result.error}")
        else:
            st.caption(f"Retrieved knowledge base docs: {', '.join(result.retrieved_doc_ids)}")

            if result.rejected:
                st.warning(f"⚠️ {len(result.rejected)} suggestion(s) blocked by guardrails (see below).")
                with st.expander("Why were suggestions blocked?"):
                    for r in result.rejected:
                        st.write(f"- {r.reason}")

            for i, suggestion in enumerate(result.accepted):
                with st.container(border=True):
                    st.write(
                        f"**{suggestion['title']}** — {suggestion['duration_minutes']} min, "
                        f"{suggestion['priority']} priority, {suggestion['frequency']}"
                        + (f", at {suggestion['time']}" if suggestion["time"] else "")
                    )
                    st.caption(suggestion["rationale"])
                    st.caption(f"Source: {', '.join(suggestion['source_doc_ids']) or 'n/a'}")
                    if st.button("Accept into task list", key=f"accept-{i}-{result_pet_name}"):
                        advisor_pet = next(pet for pet in owner.pets if pet.name == advisor_pet_name)
                        advisor_pet.add_task(
                            Task(
                                title=suggestion["title"],
                                duration_minutes=suggestion["duration_minutes"],
                                priority=suggestion["priority"],
                                time=suggestion["time"],
                                frequency=suggestion["frequency"],
                            )
                        )
                        st.success(f"Added '{suggestion['title']}' to {advisor_pet_name}'s task list.")
                        st.rerun()

st.divider()

# --- Generate schedule ---------------------------------------------------------
st.subheader("Build Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    all_tasks = owner.get_all_tasks()

    conflicts = scheduler.detect_conflicts(all_tasks)
    for warning in conflicts:
        st.warning(f"⚠️ {warning}")

    plan = scheduler.generate_plan()
    if plan.scheduled_tasks:
        st.success(f"Plan generated — {plan.total_time_used} of {owner.available_minutes} minutes used.")
    st.code(plan.display())
