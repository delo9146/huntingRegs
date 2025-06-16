import os
from dotenv import load_dotenv, find_dotenv
import json
from openai import OpenAI
from configManager import ConfigManager
from assistantManager import AssistantManager

load_dotenv(find_dotenv())

def run_query_return(state: str, species: str, prompt: str = None, inject_chunks: bool = False):
    """
    Responses API call with metadata filtering.
    If inject_chunks=True, builds the prompt using section templates and top retrieved chunks.
    """
    cfg = ConfigManager()
    am = AssistantManager(cfg)
    vs = am.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    # Step 1: Load and assemble prompt
    if inject_chunks:
        intro = cfg.summary_intro_for(state).format(state=state, species=species)
        outro = cfg.summary_outro_for(state)
        templates = cfg.section_templates_for(state)
        section_chunks = retrieve_section_chunks(state, species)

        prompt_parts = [intro.strip()]
        for section_name, section_template in templates.items():
            chunk = section_chunks.get(section_name)
            if chunk:
                enriched = f"{section_template.strip()}\n\nRetrieved Context:\n{chunk.strip()}"
            else:
                enriched = section_template.strip()
            prompt_parts.append(enriched)
        prompt_parts.append(outro.strip())

        prompt = "\n\n".join(prompt_parts)
        print(prompt)

    file_search = {
        "type": "file_search",
        "vector_store_ids": [vs.id],
        "filters": {
            "type": "and",
            "filters": [
                {"type": "eq", "key": "state", "value": state},
                {"type": "eq", "key": species, "value": True}
            ]
        }
    }

    print("=== FILE_SEARCH PAYLOAD ===")
    print(json.dumps(file_search, indent=2))
    print("===========================")

    response = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search]
    )

    return {"text": response.output_text, "annotations": []}



def retrieve_section_chunks(state: str, species: str) -> dict:
    """
    For a given state and species, run the Retrieval API for each section query defined in TOML.
    Returns a dict: { section_name: top_chunk_text }
    """
    cfg = ConfigManager()
    am = AssistantManager(cfg)
    vs = am.get_or_create_vector_store(cfg.vector_store_name)

    client = OpenAI(api_key=os.getenv(cfg.api_key_env))
    queries = cfg.sectional_queries_for(state)

    section_chunks = {}

    for section, query in queries.items():
        results = client.vector_stores.search(
            vector_store_id=vs.id,
            query=query,
            filters={
                "type": "and",
                "filters": [
                    {"type": "eq", "key": "state", "value": state},
                    {"type": "eq", "key": species, "value": True}
                ]
            },
            max_num_results=1,
            rewrite_query=False
        )

        if results.data:
            section_chunks[section] = results.data[0].content[0].text.strip()

    return section_chunks



def extract_legality_from_text(text):
    lowered = text.strip().lower()
    if lowered.startswith("yes"):
        return True
    elif lowered.startswith("no"):
        return False
    return None

