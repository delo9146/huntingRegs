import re
from configManager import ConfigManager
from assistantManager import AssistantManager
import streamlit as st

@st.cache_data(show_spinner="Fetching citation source...")
def get_chunk_text_by_citation(citation_id: str) -> str:
    """
    Look up a citation in the vector store and return its chunk text.
    """
    # Parse the citation. Usually format is 5:8†source or 5:14†2025-regulations.pdf
    try:
        match = re.match(r"(\d+):(\d+)†([^\]]+)", citation_id)
        if not match:
            return "Invalid citation format."
        message_idx, chunk_idx, file_id = match.groups()
    except Exception as e:
        return f"Failed to parse citation: {e}"

    cfg = ConfigManager()
    am = AssistantManager(cfg)
    vs = am.get_or_create_vector_store()

    chunks = am.client.vector_stores.files.list(vector_store_id=vs.id).data

    for chunk in chunks:
        if (getattr(chunk, "filename", None) and file_id in getattr(chunk, "filename")) or file_id in chunk.id:
            return f"File: {getattr(chunk, 'filename', chunk.id)}\n(No direct text access in OpenAI API—see note below.)"
    return "Citation source not found in vector store."
