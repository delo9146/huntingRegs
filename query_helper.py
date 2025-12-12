import os
from dotenv import load_dotenv, find_dotenv
import json
import re
import time
from openai import OpenAI
from configManager import ConfigManager
from ingestManager import IngestManager

load_dotenv(find_dotenv())

DRAW_KEYWORDS = (
    "draw odds", "draw-odds", "odds", "applications", "applicants",
    "bonus points", "bonus-points", "success", "successes", "point level",
    "at X points", "with X points"
)

LICENSE_RE = re.compile(r"\b\d{3}-\d{2}\b")

def is_draw_stats_question(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in DRAW_KEYWORDS)

def force_sample_size_instruction() -> str:
    return (
        "When answering, if this question involves draw odds / bonus points / applications / successes, "
        "return a short, structured summary labeled **Historical (this document’s year)** and ALWAYS include:\n"
        "- License (e.g., 320-50) and residency (resident or nonresident)\n"
        "- Point level queried\n"
        "- Applicants (denominator) and Successes (numerator)\n"
        "- Historical percentage = successes ÷ applicants (round to 1–2 decimals)\n"
        "- Quote the exact table row (evidence) and cite the page if present\n"
        "Use this compact format:\n"
        "Historical {YEAR} — {LICENSE} ({RESIDENCY}), {POINTS} pts: {SUCCESSES}/{APPLICANTS} = {PCT}%\n"
        "Evidence: “{QUOTED_ROW}”"
    )

def run_query_return(state: str, species: str, prompt: str = None, inject_chunks: bool = False):
    """
    Responses API call with metadata filtering.
    Now automatically splits all sections into 4 smaller parts (≈ equal size)
    to prevent token-limit errors.
    """
    start_time = time.time()
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    # --- Load templates and retrievals ---
    intro = cfg.summary_intro_for(state) or ""
    outro = cfg.summary_outro_for(state) or ""
    templates = cfg.section_templates_for(state)
    section_chunks = retrieve_section_chunks(state, species) if inject_chunks else {}

    # --- Build enriched section blocks ---
    section_blocks = []
    for section_name, section_template in templates.items():
        chunk = (section_chunks.get(section_name) or "").strip()
        if inject_chunks and chunk:
            enriched = (
                f"{section_template.strip()}\n\n"
                f"Reference the excerpt below, which was retrieved by OpenAI’s Retrieval API using a section-specific query. "
                f"This result complements the current file search to help you generate an accurate and detailed summary for this section.\n"
                f"{chunk}"
            )
        else:
            enriched = section_template.strip()
        section_blocks.append(enriched)

    # --- Divide into 4 roughly equal parts ---
    total = len(section_blocks)
    split_size = max(1, total // 4)
    parts = [section_blocks[i:i + split_size] for i in range(0, total, split_size)]

    # Add intro/outro boundaries
    prompt_parts = []
    for idx, blocks in enumerate(parts):
        if idx == 0:
            header = f"{intro.strip()}\n\nBegin Part {idx+1}. Write sections 1–{split_size}."
        elif idx == len(parts) - 1:
            header = (
                f"Continue with the remaining sections ({(idx*split_size)+1}–{total}). "
                "Do **not** skip any section. Include at least one bullet under each. "
                "Maintain the same markdown style. Finish with a concise summary.\n"
            )
        else:
            header = (
                f"Continue with sections {(idx*split_size)+1}–{(idx+1)*split_size}. "
                "Do **not** skip any section. Maintain same markdown formatting.\n"
            )
        footer = outro.strip() if idx == len(parts) - 1 else f"End Part {idx+1}. Do not include a conclusion."
        prompt_parts.append("\n\n".join([header, *blocks, footer]))

    # --- File search tool definition ---
    file_search = {
        "type": "file_search",
        "vector_store_ids": [vs.id],
        "filters": {
            "type": "and",
            "filters": [
                {"type": "eq", "key": "state", "value": state.lower()},
                {"type": "eq", "key": species, "value": True},
            ],
        },
    }

    print("=== FILE_SEARCH PAYLOAD ===")
    print(json.dumps(file_search, indent=2))
    print("===========================")

    # --- Helper for safe call with retry ---
    def _with_retry(call_fn, label, max_retries=3):
        delay = 5.0
        for attempt in range(max_retries):
            try:
                return call_fn()
            except Exception as e:
                msg = str(e)
                if "rate_limit_exceeded" in msg or "Rate limit reached" in msg:
                    print(f"[{label}] 429 rate limit. Retry {attempt+1}/{max_retries} after {delay:.1f}s")
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        raise RuntimeError(f"{label} failed after {max_retries} retries.")

    # --- Run each part sequentially ---
    all_texts = []
    for i, part_prompt in enumerate(prompt_parts, start=1):
        print(f"\n=== Running Part {i}/{len(prompt_parts)} ===")
        response = _with_retry(
            lambda: client.responses.create(
                model=cfg.model_name,
                input=part_prompt,
                tools=[file_search],
                temperature=0,
            ),
            label=f"Part {i}",
        )
        text_part = getattr(response, "output_text", None) or str(response)
        all_texts.append(text_part)
        # gentle pause between parts
        time.sleep(5.0)

    combined_text = "\n\n".join(all_texts)

    total_time = time.time() - start_time
    print(f"\n=== TOTAL SUMMARY TIME: {total_time:.2f} seconds ({total_time/60:.2f} minutes) ===\n")


    return {"text": combined_text, "annotations": []}





def retrieve_section_chunks(state: str, species: str) -> dict:
    """
    For a given state and species, run the Retrieval API for each section query defined in TOML.
    Returns a dict: { section_name: top_chunk_text }
    """
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)

    client = OpenAI(api_key=os.getenv(cfg.api_key_env))
    queries = cfg.sectional_queries_for(state)

    section_chunks = {}
    #retrieval API/vector_stores.search()
    for section, query_template in queries.items():
        query = query_template.format(species=species)
        results = client.vector_stores.search(
            vector_store_id=vs.id,
            query=query,
            filters={
                "type": "and",
                "filters": [
                    {"type": "eq", "key": "state", "value": state.lower()},
                    {"type": "eq", "key": species, "value": True}
                ]
            },
            max_num_results=2,
            rewrite_query=True
        )


        if results.data:
            section_chunks[section] = "\n---\n".join(
                [r.content[0].text.strip() for r in results.data]
            )


    return section_chunks



def extract_legality_from_text(text):
    lowered = text.strip().lower()
    if lowered.startswith("yes"):
        return True
    elif lowered.startswith("no"):
        return False
    return None

def run_prompt_simple(prompt: str) -> dict:
    """
    Minimal Responses API call with NO tools / NO vector store.
    Use for non-RAG tasks like the DOPE calculator.
    """
    cfg = ConfigManager()
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    response = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        temperature = 0,
        top_p = 1
    )
    return {"text": response.output_text}


def run_legality_query(state: str, species: str, prompt: str) -> dict:
    """
    Lightweight one-shot query for legality or species/unit questions.
    Avoids section-splitting and runs a single, fast LLM call.
    """
    start_time = time.time()
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    # Define file_search tool with state + species filters (for contextual accuracy)
    file_search = {
        "type": "file_search",
        "vector_store_ids": [vs.id],
        "filters": {
            "type": "and",
            "filters": [
                {"type": "eq", "key": "state", "value": state.lower()},
                {"type": "eq", "key": species, "value": True},
            ],
        },
    }

    print("=== LEGALITY FILE_SEARCH PAYLOAD ===")
    print(json.dumps(file_search, indent=2))
    print("===========================")

    # Create and send a single short query
    response = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search],
        temperature=0,
    )

    total_time = time.time() - start_time
    print(f"\n=== LEGALITY QUERY TIME: {total_time:.2f}s ({total_time/60:.2f}m) ===\n")

    return {"text": response.output_text, "annotations": []}

def run_harvest_query(state: str, species: str, unit: str, year: int) -> dict:
    """
    File search limited to harvest_report=True for the given state/species.
    Returns STRICT JSON in the .text field.
    """
    start_time = time.time()
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    # Limit retrieval to harvest report files for the chosen state/species
    file_search = {
        "type": "file_search",
        "vector_store_ids": [vs.id],
        "filters": {
            "type": "and",
            "filters": [
                {"type": "eq", "key": "state", "value": state.lower()},
                {"type": "eq", "key": species, "value": True},
                {"type": "eq", "key": "harvest_report", "value": True},
            ],
        },
    }

    # STRICT JSON prompt (no prose, no markdown, no code fences)
    harvest_prompt = (
        "You are answering ONLY from the harvest report (metadata harvest_report=True). "
        f"Return a STRICT JSON object for {species} in unit {unit} for {year}. "
        "If no exact row exists, return {\"found\": false, \"reason\": \"...\"}.\n\n"
        "Schema:\n"
        "{\n"
        "  \"found\": true,\n"
        "  \"unit\": \"<unit>\",\n"
        "  \"year\": <int>,\n"
        "  \"resident\": {\"hunters\": <int|null>, \"harvest\": <int|null>},\n"
        "  \"nonresident\": {\"hunters\": <int|null>, \"harvest\": <int|null>},\n"
        "  \"sum\": {\"hunters\": <int|null>, \"harvest\": <int|null>}\n"
        "}\n\n"
        "Rules: JSON ONLY. No markdown. No code fences. No explanation."
    )

    response = client.responses.create(
        model=cfg.model_name,
        input=harvest_prompt,
        tools=[file_search],
        temperature=0,
    )

    total_time = time.time() - start_time
    print(f"\n=== HARVEST QUERY TIME: {total_time:.2f}s ===\n")

    # IMPORTANT: return a dict with a 'text' string so appManager can json.loads(...)
    return {"text": response.output_text, "annotations": []}



def run_qa_query(state: str, species: str, question: str) -> dict:
    """
    One-shot Q&A over regs for the given state/species.
    Uses file_search with metadata filters. No splitting.
    """
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))

    file_search = {
        "type": "file_search",
        "vector_store_ids": [vs.id],
        "filters": {
            "type": "and",
            "filters": [
                {"type": "eq", "key": "state", "value": state.lower()},
                {"type": "eq", "key": species, "value": True},
            ],
        },
    }

    prompt = (
        "Answer succinctly based only on the attached regulations. "
        "If you cite dates or unit rules, include the unit name if present. "
        "If unknown, say you cannot find it.\n\n"
        f"Q: {question}"
    )

    resp = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search],
        temperature=0,
    )
    return {"text": resp.output_text}





