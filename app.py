import streamlit as st
from configManager import ConfigManager
from query_helper import run_query_return  # from Step 1

cfg = ConfigManager()
available_states = [] 
available_species = cfg.valid_species

import os
input_dir = cfg.input_dir
if os.path.exists(input_dir):
    available_states = [
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
else:
    available_states = ["MT", "CO"] 

st.title("Hunting Regulations AI Demo")
st.write("Select a state and species to see a summary of hunting regulations. Then, ask specific questions.")

state = st.selectbox("Select state", available_states)
species = st.selectbox("Select species", available_species)

if "last_state" not in st.session_state:
    st.session_state.last_state = None
if "last_species" not in st.session_state:
    st.session_state.last_species = None

auto_summary = ""
if state and species:
    if (
        st.session_state.last_state != state
        or st.session_state.last_species != species
    ):
        with st.spinner(f"Summarizing regulations for {state} - {species}..."):
            summary_prompt = (
                f"Summarize the hunting regulations for {state} for {species}. "
                "Include seasons, tag types, quotas, regions/units, weapon restrictions, and unique rules."
            )
            auto_summary = run_query_return(state, summary_prompt)
            st.session_state.auto_summary = auto_summary
        st.session_state.last_state = state
        st.session_state.last_species = species
    else:
        auto_summary = st.session_state.get("auto_summary", "")

if auto_summary:
    st.subheader(f"Summary for {state} - {species}")
    st.markdown(auto_summary)

st.divider()
st.markdown("**Ask a specific question about the regulations:**")

# --- Initialize chat history ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "prompt" not in st.session_state:
    st.session_state.prompt = ""

user_prompt = st.text_area("Question", key="prompt", value=st.session_state.prompt, placeholder="Type your regulation question here...")

ask_btn = st.button("Ask", key="ask_button")

if ask_btn and user_prompt and state:
    with st.spinner("Getting answer..."):
        answer = run_query_return(state, user_prompt)
        # Save the Q&A to chat history
        st.session_state.chat_history.append((user_prompt, answer))

# Optional: Reset Button to Clear Chat
if st.button("Clear Conversation"):
    st.session_state.chat_history = []

# Display Chat History (all Q&A)
if st.session_state.chat_history:
    st.markdown("## Conversation History")
    for i, (q, a) in enumerate(st.session_state.chat_history, 1):
        st.markdown(f"**Q{i}:** {q}")
        st.markdown(f"**A{i}:** {a}")
        st.divider()


