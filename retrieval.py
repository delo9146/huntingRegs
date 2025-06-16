# retrieval_debug.py
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from configManager import ConfigManager
from assistantManager import AssistantManager

def run_retrieval_debug(query: str, state: str, species: str, top_k: int = 5):
    load_dotenv()
    cfg = ConfigManager()
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    am = AssistantManager(cfg)
    vs = am.get_or_create_vector_store(cfg.vector_store_name)

    filters = {
        "type": "and",
        "filters": [
            {"type": "eq", "key": "state", "value": state},
            {"type": "eq", "key": species, "value": True}
        ]
    }

    print("=== SENDING TO RETRIEVAL API ===")
    print(f"Query: {query}")
    print(f"Filters: {json.dumps(filters, indent=2)}")
    print(f"Vector Store: {vs.id}")
    print("===============================")

    results = client.vector_stores.search(
        vector_store_id=vs.id,
        query=query,
        filters=filters,
        max_num_results=top_k,
        rewrite_query=False  # Optional, but makes debugging more transparent
    )


    print(f"\nTop {top_k} Retrieved Chunks:\n")
    for i, r in enumerate(results.data, 1):
        print(f"[{i}] Score: {r.score}")
        print(f"File: {r.filename} (ID: {r.file_id})")
        print(f"Attributes: {r.attributes or '{}'}")
        print(f"Text:\n{r.content[0].text[:800]}{'...' if len(r.content[0].text) > 800 else ''}")
        print("-" * 80)



if __name__ == "__main__":
    cfg = ConfigManager()
    state = "Montana"
    species = "elk"
    summary_prompt = cfg.summary_prompt_for(state).format(
        state=state,
        species=species
    )

    run_retrieval_debug(
        query=summary_prompt,
        state=state,
        species=species,
        top_k=10
    )

