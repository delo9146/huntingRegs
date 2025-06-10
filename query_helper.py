import os
from dotenv import load_dotenv, find_dotenv
import json
from openai import OpenAI
from configManager import ConfigManager
from assistantManager import AssistantManager

load_dotenv(find_dotenv())

def run_query_return(state: str, species: str, prompt: str):
    """
    Single-shot Responses API call with metadata filtering.
    Includes debug steps:
      1) Print the file_search payload
      2) Perform a metadata-only vector store search
    Returns dict with 'text' and empty 'annotations'.
    """

    cfg = ConfigManager()
    am = AssistantManager(cfg)

    vs = am.get_or_create_vector_store(cfg.vector_store_name)

    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

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

    resp = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search]
    )

    return {"text": resp.output_text, "annotations": []}


def extract_legality_from_text(text):
    lowered = text.strip().lower()
    if lowered.startswith("yes"):
        return True
    elif lowered.startswith("no"):
        return False
    return None

