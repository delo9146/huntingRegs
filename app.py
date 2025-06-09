import streamlit as st
import re
import os
import datetime
from configManager import ConfigManager
from query_helper import run_query_return

cfg = ConfigManager()

# build lists of available states & species (for the Regulations UI)
input_dir = cfg.input_dir
if os.path.exists(input_dir):
    available_states = [
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
else:
    available_states = ["MT", "CO"]
available_species = cfg.valid_species

# ─── build species→units mapping for Montana from regulations.toml ────────────
species_to_units = {
    sp: cfg.units_for("Montana", sp)
    for sp in cfg.valid_species
    if cfg.units_for("Montana", sp)
}

# ─── Regulations UI ───────────────────────────────────────────────────────────
def show_regulations_ui():
    # back button
    st.button(
        "⬅️ Back to Home",
        on_click=lambda: st.session_state.pop("page", None)
    )

    st.title("Hunting Regulations AI Demo")
    st.write("Select a state and species to see a summary. Then ask specific questions.")

    state = st.selectbox("Select state", available_states)
    species = st.selectbox("Select species", available_species)

    # ensure session-state slots exist
    st.session_state.setdefault("auto_summary", "")
    st.session_state.setdefault("auto_summary_annotations", [])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("prompt", "")

    # Generate Summary
    if st.button("Generate Summary"):
        with st.spinner(f"Summarizing {state} – {species}…"):
            summary_prompt = cfg.summary_prompt.format(
                state=state,
                species=species
            )
            res = run_query_return(state, species, summary_prompt)
            st.session_state.auto_summary = res["text"]
            st.session_state.auto_summary_annotations = res.get("annotations", [])

    # Display Summary if present
    if st.session_state.auto_summary:
        st.subheader(f"Summary for {state} – {species}")
        st.markdown(st.session_state.auto_summary, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Ask a specific question:**")

    # Q&A
    user_q = st.text_area(
        "Your question",
        key="prompt",
        value=st.session_state.prompt,
        placeholder="Type your regulation question here…"
    )
    if st.button("Ask"):
        with st.spinner("Getting answer…"):
            ans = run_query_return(state, species, user_q)
            st.session_state.chat_history.append((user_q, ans))

    if st.button("Clear Conversation"):
        st.session_state.chat_history = []

    if st.session_state.chat_history:
        st.markdown("## Conversation History")
        for i, (q, a) in enumerate(st.session_state.chat_history, 1):
            st.markdown(f"**Q{i}:** {q}")
            st.markdown(a["text"], unsafe_allow_html=True)
            st.divider()

# ─── Species/Unit Demo UI ───────────────────────────────────────────────────────
def show_unit_demo_ui():
    # back button
    st.button(
        "⬅️ Back to Home",
        on_click=lambda: st.session_state.pop("page", None)
    )

    st.title("📍 Species / Unit Demo")
    st.write("Select a state, species, and unit to see all regulations for that combination, and whether the species can be hunted today.")

    # 1) Select state (only Montana for demo)
    state = st.selectbox("Select state", ["Montana"])

    # 2) Select species (only those with units in Montana)
    species = st.selectbox("Select species", list(species_to_units.keys()))

    # 3) Select unit for that species
    unit = st.selectbox("Select HD/Unit", species_to_units[species])

    # 4) On click, query regs + current-open status
    if st.button(f"Show regs for {species.capitalize()} in HD {unit}"):
        today_str = datetime.date.today().strftime("%B %d, %Y")
        prompt = cfg.unit_prompt.format(
            state=state,
            species=species.capitalize(),
            unit=unit,
            today_str=today_str
        )
        with st.spinner(f"Querying regs for {species.capitalize()} in HD {unit}…"):
            res = run_query_return(state, species, prompt)
        st.markdown(res["text"], unsafe_allow_html=True)

# ─── Home Directory ───────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.title("🔧 AI-Tool Directory")
    st.write("Select a demo to run:")

    st.button(
        "🎯 Hunting Regulations",
        on_click=lambda: st.session_state.__setitem__("page", "regs")
    )
    st.button(
        "📍 Species / Unit Demo",
        on_click=lambda: st.session_state.__setitem__("page", "demo")
    )

    # if still no choice, halt here
    if "page" not in st.session_state:
        st.stop()

# ─── Branch to the selected page ───────────────────────────────────────────────
if st.session_state.page == "regs":
    show_regulations_ui()
elif st.session_state.page == "demo":
    show_unit_demo_ui()
