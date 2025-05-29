import re
from configManager import ConfigManager
from assistantManager import AssistantManager
import streamlit as st
from openai import OpenAI
import os

@st.cache_data(show_spinner="Fetching citation source...")
def get_chunk_text_by_citation(citation_id: str) -> str:
    """
    Look up a citation in the vector store and return its chunk text.
    Requires OpenAI's new vector store file content API.
    """
    # Parse the citation. Format: 5:8†file-abc123
    match = re.match(r"(\d+):(\d+)†([^\]]+)", citation_id)
    if not match:
        return "Invalid citation format."

    message_idx, chunk_idx, file_id = match.groups()
    chunk_idx = int(chunk_idx)

    # Get config info
    cfg = ConfigManager()
    vector_store_id = "vs_68278c6a883c8191a0da6e4afc22f6bd"
    # Handle case where config might store the name, not the actual ID.
    # If you know your vector_store_id is not a human-readable name, set it directly here.

    # OpenAI API key
    api_key = os.getenv(cfg.api_key_env)
    if not api_key:
        return "No OpenAI API key found."

    client = OpenAI(api_key=api_key)

    try:
        # Get the parsed file content from the vector store
        resp = client.vector_stores.files.content(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        content_chunks = resp["content"]

        # Find the correct chunk by index
        if 0 <= chunk_idx < len(content_chunks):
            chunk = content_chunks[chunk_idx]
            if chunk["type"] == "text":
                return chunk["text"]
            else:
                return f"(Non-text chunk type: {chunk['type']})"
        else:
            return f"Chunk index {chunk_idx} out of range for this file ({len(content_chunks)} chunks found)."
    except Exception as e:
        return f"Error retrieving chunk: {e}"
