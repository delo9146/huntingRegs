import streamlit as st
import re
import os
from configManager import ConfigManager
from query_helper import run_query_return 

cfg = ConfigManager()
available_states = [] 
available_species = cfg.valid_species

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

if "auto_summary" not in st.session_state:
    st.session_state.auto_summary = ""
if "last_state" not in st.session_state:
    st.session_state.last_state = None
if "last_species" not in st.session_state:
    st.session_state.last_species = None

summary_btn = st.button("Generate Summary", key="summary_button")

if summary_btn and state and species:
    with st.spinner(f"Summarizing regulations for {state} - {species}..."):
        summary_prompt = (
            f"You are an expert at summarizing complex hunting regulations for users who are planning a hunt. "
            f"Provide a clear, concise, and detailed summary of the {state} hunting regulations for {species}, including the following sections: \n"
            "- Season dates and types (archery, general, muzzleloader, etc.)\n"
            "- Tag and license types available (resident/nonresident, quotas, preference/draw info)\n"
            "- Application deadlines and how to apply\n"
            "- Units, regions, or districts where hunting is permitted, including any notable closures or access restrictions\n"
            "- Bag limits and restrictions (sex/age, antler point, etc.)\n"
            "- Legal weapons and equipment for each season\n"
            "- Hunter orange/safety requirements\n"
            "- Special opportunities (SuperTags, youth/senior hunts, landowner tags, auctions)\n"
            "- Mandatory reporting or check-in requirements\n"
            "- Any significant rule changes, penalties, or special notes for this year\n\n"
            "Format the summary with headers and bullet points. Use clear, direct language. "
            "Use direct quotes or close paraphrasing so that citations are automatically attached."
            "Do not use human-readable placeholders like [source] or [1]. Instead, include actual OpenAI-style citations such as [5:7†file-abc123def456]."
            "These citations will automatically reference document chunks retrieved from the file_search tool. Include them where appropriate throughout the summary."

        )

        summary_result = run_query_return(state, summary_prompt)
        st.session_state.auto_summary = summary_result["text"]
        st.session_state.auto_summary_annotations = summary_result["annotations"]
        st.session_state.last_state = state
        st.session_state.last_species = species
        print("Annotations from summary:", summary_result["annotations"])

if st.session_state.auto_summary:
    st.subheader(f"Summary for {state} - {species}")
    st.markdown(st.session_state.auto_summary, unsafe_allow_html=True)


st.divider()
st.markdown("**Ask a specific question about the regulations:**")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "prompt" not in st.session_state:
    st.session_state.prompt = ""

user_prompt = st.text_area("Question", key="prompt", value=st.session_state.prompt, placeholder="Type your regulation question here...")

ask_btn = st.button("Ask", key="ask_button")

if ask_btn and user_prompt and state:
    with st.spinner("Getting answer..."):
        answer = run_query_return(state, user_prompt)
        st.session_state.chat_history.append((user_prompt, answer))

if st.button("Clear Conversation"):
    st.session_state.chat_history = []

if st.session_state.chat_history:
    st.markdown("## Conversation History")
    for i, (q, a) in enumerate(st.session_state.chat_history, 1):
        st.markdown(f"**Q{i}:** {q}")
        st.markdown(a["text"], unsafe_allow_html=True)
        st.divider()





