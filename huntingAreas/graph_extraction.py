import os
import json
from datetime import datetime

from openai import OpenAI
from configManager import ConfigManager
from ingestManager import IngestManager

# --------------------------------------------------------------------
# 1. Setup helpers: client + vector store + file_search tool
# --------------------------------------------------------------------

def _get_client_and_vector_store():
    """
    Initialize OpenAI client and get/create the regulations vector store,
    using the same pattern as query_helper.run_query_return.
    """
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))
    return cfg, client, vs


def _build_file_search_tool(state: str, species: str, vs) -> dict:
    """
    Build the file_search tool definition filtered by state + species.
    Mirrors what you do in run_query_return/run_qa_query.
    """
    return {
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

# --------------------------------------------------------------------
# 2. Prompt construction
# --------------------------------------------------------------------

def build_extraction_prompt(state: str, species: str, year: int) -> str:
    """
    Build the instructions the LLM will follow to output structured JSON
    for the given state/species/year. This is where we embed our JSON schema.
    """

    # NOTE: This is where you paste / refine the JSON schema description
    # we designed earlier. Keep it VERY explicit and emphasize:
    # - JSON ONLY
    # - Dates in YYYY-MM-DD
    # - Use only units, seasons, tags that you can confirm from the docs.

    schema_description = """
    You are extracting hunting regulations into STRICT JSON.

    Your task:
    - Focus on state-level hunting regulations for {state}, species {species}, for the {year} season.
    - Use ONLY the attached regulation documents. If something is unknown, omit it.

    Output format (single JSON object):

    {
      "state": "<full state name>",
      "year": <int>,
      "species": "<species name, e.g., elk>",
      "units": [
        {
          "unit_code": "320",
          "unit_name": "Bridger Mountains",   // if present, otherwise null or omit
          "seasons": [
            {
              "weapon": "archery",            // normalized category
              "season_type": "archery",       // e.g., general, archery, late, shoulder, youth
              "start_date": "2025-09-06",     // YYYY-MM-DD
              "end_date": "2025-10-19",
              "licenses_required": [
                {
                  "code": "General Elk",
                  "residency": "either"       // resident, nonresident, or either
                }
              ],
              "restrictions": [
                {
                  "type": "antler",           // antler, blaze_orange, vehicle_access, land_access, youth_only, etc.
                  "summary": "Brow tine bull only.",
                  "details": "Only elk with at least one brow tine of 4 inches or longer..."
                }
              ],
              "source": {
                "document_name": "2025 Montana Elk Regulations",
                "page_number": 12
              }
            }
          ],
          "unit_restrictions": [
            {
              "type": "access",
              "summary": "No motorized vehicles beyond posted signs.",
              "details": "Motorized travel is restricted to open designated routes...",
              "source": {
                "document_name": "2025 Montana Elk Regulations",
                "page_number": 8
              }
            }
          ]
        }
      ],
      "statewide_restrictions": [
        {
          "type": "blaze_orange",
          "summary": "Blaze orange required during general firearms seasons.",
          "details": "Hunters must wear at least 400 square inches of hunter orange...",
          "source": {
            "document_name": "2025 Montana General Regulations",
            "page_number": 3
          }
        }
      ]
    }

    Rules:
    - JSON ONLY. No markdown, no comments, no code fences.
    - Dates MUST be "YYYY-MM-DD".
    - Only include units, seasons, licenses, and restrictions that you can confidently identify.
    - If a field is unknown, omit it rather than guessing.
    """.format(state=state, species=species, year=year)

    return schema_description.strip()

# --------------------------------------------------------------------
# 3. Call the LLM with file_search
# --------------------------------------------------------------------

def call_extraction_llm(state: str, species: str, year: int) -> str:
    """
    Use the Responses API + file_search to extract structured JSON.
    Returns the raw text output from the model (should be JSON).
    """
    cfg, client, vs = _get_client_and_vector_store()
    file_search_tool = _build_file_search_tool(state, species, vs)
    prompt = build_extraction_prompt(state, species, year)

    response = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search_tool],
        temperature=0,
    )
    # All your other code uses response.output_text; keep it consistent.
    return response.output_text

# --------------------------------------------------------------------
# 4. Parse + basic validation
# --------------------------------------------------------------------

def parse_and_validate_json(raw_text: str, state: str, species: str, year: int) -> dict:
    """
    Parse the model output as JSON and perform some basic sanity checks.
    Raise ValueError if things look wrong so you can debug / retry.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model output was not valid JSON: {e}\n\nRaw:\n{raw_text[:500]}")

    # Basic checks
    if str(data.get("state", "")).lower().replace(" ", "") == state.lower().replace(" ", ""):
        pass  # okay-ish
    # You can decide how strict you want to be here.

    if data.get("species") and data["species"].lower() != species.lower():
        # Not fatal, but warn or raise depending on how strict you want
        raise ValueError(f"Extracted species {data['species']} != expected {species}")

    if "year" in data and int(data["year"]) != int(year):
        raise ValueError(f"Extracted year {data['year']} != expected {year}")

    # Optional: validate dates in seasons
    for unit in data.get("units", []):
        for season in unit.get("seasons", []):
            for key in ("start_date", "end_date"):
                if key in season:
                    try:
                        datetime.strptime(season[key], "%Y-%m-%d")
                    except Exception as e:
                        raise ValueError(f"Invalid date {season[key]} in season: {e}")

    return data

# --------------------------------------------------------------------
# 5. Orchestration: run extraction + write to file
# --------------------------------------------------------------------

def extract_reg_graph(state: str, species: str, year: int, output_dir: str = "output/graph") -> str:
    """
    High-level entrypoint:
    - Calls the LLM with file_search
    - Parses and validates JSON
    - Writes JSON to output_dir as <state>_<species>_<year>.json
    - Returns the output file path
    """
    raw = call_extraction_llm(state, species, year)
    data = parse_and_validate_json(raw, state, species, year)

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{state.lower()}_{species.lower()}_{year}.json".replace(" ", "_")
    out_path = os.path.join(output_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return out_path

# --------------------------------------------------------------------
# 6. Optional: simple CLI runner for manual testing
# --------------------------------------------------------------------

if __name__ == "__main__":
    # Simple manual test; tweak these values as needed.
    # For Montana elk 2025, you'd run: python graph_extraction.py
    state = "Montana"
    species = "elk"
    year = 2025

    path = extract_reg_graph(state, species, year)
    print(f"Wrote structured regulations JSON to: {path}")
