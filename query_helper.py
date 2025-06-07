import os
from dotenv import load_dotenv, find_dotenv
import json
from openai import OpenAI
from configManager import ConfigManager
from assistantManager import AssistantManager

# Load environment variables from .env
load_dotenv(find_dotenv())

def run_query_return(state: str, species: str, prompt: str):
    """
    Single-shot Responses API call with metadata filtering.
    Includes debug steps:
      1) Print the file_search payload
      2) Perform a metadata-only vector store search
    Returns dict with 'text' and empty 'annotations'.
    """
    # Initialize config and manager
    cfg = ConfigManager()
    am = AssistantManager(cfg)

    # Ensure vector store exists
    vs = am.get_or_create_vector_store(cfg.vector_store_name)

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    # Build file_search tool with boolean species filter (use 'key' not 'property')
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

    # Debug Step 1: log payload
    print("=== FILE_SEARCH PAYLOAD ===")
    print(json.dumps(file_search, indent=2))
    print("===========================")

    # Single-shot Responses API call
    resp = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search]
    )

    # Return the generated text
    return {"text": resp.output_text, "annotations": []}
