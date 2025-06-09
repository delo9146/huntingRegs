import streamlit as st
import re
import os
from configManager import ConfigManager
from query_helper import run_query_return

cfg = ConfigManager()

# build lists of available states & species
input_dir = cfg.input_dir
if os.path.exists(input_dir):
    available_states = [
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
else:
    available_states = ["MT", "CO"]
available_species = cfg.valid_species

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
            summary_prompt = (
            f"You are an expert at summarizing complex hunting regulations for users who are planning a hunt. "
            f"Provide a clear, concise, and extremely detailed summary of the {state} hunting regulations for {species}, including the following sections: \n"
            "- Season dates and types (archery, general, muzzleloader, etc.)\n"
            "- Tag and license types available (resident/nonresident, quotas, preference/draw info)\n"
            "- Application deadlines and how to apply\n"
            "- Units, regions, or districts where hunting is permitted, including any notable closures or access restrictions\n"
            "- Bag limits and restrictions (sex/age, antler point, etc.)\n"
            "- Legal weapons and equipment for each season\n"
            "- Hunter orange/safety requirements. Specifically, if mentioned, how much orange.\n"
            "- Special opportunities (SuperTags, youth/senior hunts, landowner tags, auctions)\n"
            "- Mandatory reporting or check-in requirements\n"
            "- Any significant rule changes, penalties, or special notes for this year\n\n"
            "Format the summary with headers and bullet points. Use clear, direct language. "
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

    st.title("Species / Unit Demo")
    st.write("🔨 This page is under construction. Your species / unit picker goes here.")

# ─── Home Directory ───────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.title("🔧 AI-Tool Directory")
    st.write("Select a demo to run:")

    # clicking sets session_state.page
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
