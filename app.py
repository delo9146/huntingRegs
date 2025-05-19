import streamlit as st
from configManager import ConfigManager
from query_helper import run_query_return  # from Step 1

# --- Load config ---
cfg = ConfigManager()
available_states = []  # Will fill from vector store files or config
available_species = cfg.valid_species

# For demo, let’s scan the input_dir for state folders
import os
input_dir = cfg.input_dir
if os.path.exists(input_dir):
    available_states = [
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
else:
    available_states = ["MT", "CO"]  # fallback

st.title("Hunting Regulations AI Demo")
st.write("Select a state and species to see a summary of hunting regulations. Then, ask specific questions.")

# --- UI Components ---
state = st.selectbox("Select state", available_states)
species = st.selectbox("Select species", available_species)

if "last_state" not in st.session_state:
    st.session_state.last_state = None
if "last_species" not in st.session_state:
    st.session_state.last_species = None

# --- Auto summary on state/species change ---
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

# --- User prompt for detailed questions ---
st.divider()
st.markdown("**Ask a specific question about the regulations:**")
user_prompt = st.text_area("Question", key="prompt")
ask_btn = st.button("Ask")

if ask_btn and user_prompt and state:
    with st.spinner("Getting answer..."):
        answer = run_query_return(state, user_prompt)
        st.markdown("### Assistant Response")
        st.markdown(answer)
