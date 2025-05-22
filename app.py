import streamlit as st
import re
import os
from configManager import ConfigManager
from query_helper import run_query_return 
from citation_helper import get_chunk_text_by_citation

def render_with_clickable_citations(text, key_prefix=""):
    """
    Render markdown text with citations like [5:3†source] as clickable buttons.
    """
    text = text.replace("【", "[").replace("】", "]")
    citation_pattern = r'(\[\d+:\d+†[^\]]+\])'
    parts = re.split(citation_pattern, text)
    for i, part in enumerate(parts):
        match = re.match(r'\[(\d+:\d+†[^\]]+)\]', part)
        if match:
            citation = match.group(1)
            # Show as a button
            if st.button(f"See Source: {citation}", key=f"{key_prefix}_{citation}_{i}"):
                st.session_state['selected_citation'] = citation.strip("[]")

        else:
            # Still render regular text
            st.markdown(part, unsafe_allow_html=True)


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

left_col, right_col = st.columns([2, 1])

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
            "Include citations to the original document where appropriate."
        )

        st.session_state.auto_summary = run_query_return(state, summary_prompt)
        st.session_state.last_state = state
        st.session_state.last_species = species

with left_col:
    if st.session_state.auto_summary:
        st.subheader(f"Summary for {state} - {species}")
        render_with_clickable_citations(st.session_state.auto_summary, key_prefix="summary")

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

with left_col:
    # ... summary above ...
    if st.session_state.chat_history:
        st.markdown("## Conversation History")
        for i, (q, a) in enumerate(st.session_state.chat_history, 1):
            st.markdown(f"**Q{i}:** {q}")
            render_with_clickable_citations(a, key_prefix=f"chat_{i}")
            st.divider()

with right_col:
    st.subheader("Citation Source")
    selected_citation = st.session_state.get('selected_citation')
    if selected_citation:
        chunk_text = get_chunk_text_by_citation(selected_citation)
        st.markdown(f"**Citation ID:** `{selected_citation}`")
        st.markdown(chunk_text)
    else:
        st.write("Click a citation to view its source context here.")



