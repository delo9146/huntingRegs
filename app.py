import streamlit as st
import re
import os
from configManager import ConfigManager
from query_helper import run_query_return 
from citation_helper import get_chunk_text_by_citation

def normalize_cite(text):
    return text.replace("【", "[").replace("】", "]").strip().strip("[]")

def render_with_clickable_citations(text, annotations, key_prefix=""):
    text = str(text)
    text = text.replace("【", "[").replace("】", "]")
    citation_pattern = r'(\[\d+:\d+†[^\]]+\])'
    parts = re.split(citation_pattern, text)

    char_index = 0
    for i, part in enumerate(parts):
        # See if part is a citation marker
        match = re.match(r'\[(\d+:\d+†[^\]]+)\]', part)
        if match:
            citation = match.group(0)
            annotation = next(
                (a for a in annotations if citation in str(a)),  # Match on actual citation ID
                None
            )
            if st.button(f"See Source: {citation}", key=f"{key_prefix}_{citation}_{i}"):
                st.session_state['selected_citation'] = citation
                st.session_state['selected_annotation'] = annotation
            char_index += len(part)
        else:
            st.markdown(part, unsafe_allow_html=True)
            char_index += len(part)


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
            "Use direct quotes or close paraphrasing so that citations are automatically attached."
            "Do not use human-readable placeholders like [source] or [1]. Instead, include actual OpenAI-style citations such as [5:7†file-abc123def456]."
            "These citations will automatically reference document chunks retrieved from the file_search tool. Include them where appropriate throughout the summary."

        )

        summary_result = run_query_return(state, summary_prompt)
        st.session_state.auto_summary = summary_result["text"]
        st.session_state.auto_summary_annotations = summary_result["annotations"]
        st.session_state.last_state = state
        st.session_state.last_species = species

with left_col:
    if st.session_state.auto_summary:
        st.subheader(f"Summary for {state} - {species}")
        render_with_clickable_citations(
            st.session_state.auto_summary,
            st.session_state.get("auto_summary_annotations", []),
            key_prefix="summary"
    )


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
        st.markdown(f"**Citation ID:** `{selected_citation}`")
        with st.spinner("Retrieving source text..."):
            source_text = get_chunk_text_by_citation(selected_citation)
        st.markdown(f"**Source Text:**\n\n{source_text}")
    else:
        st.write("Click a citation to view its source context here.")




