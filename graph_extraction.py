import os
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from configManager import ConfigManager
from ingestManager import IngestManager

# --------------------------------------------------------------------
# 1. Setup helpers: client + vector store + file_search tool
# --------------------------------------------------------------------

def _get_client_and_vector_store() -> Tuple[ConfigManager, OpenAI, Any]:
    """
    Initialize OpenAI client and get/create the regulations vector store,
    using the same pattern as query_helper.run_query_return.
    """
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))
    return cfg, client, vs


def _build_file_search_tool(state: str, species: str, vs: Any) -> Dict[str, Any]:
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

def _format_unit_list(unit_codes: List[str], max_line_len: int = 110) -> str:
    """
    Format unit codes into wrapped lines so the prompt stays readable.
    """
    units = [str(u).strip() for u in unit_codes if str(u).strip()]
    line = ""
    lines = []
    for u in units:
        token = (u + ", ")
        if len(line) + len(token) > max_line_len and line:
            lines.append(line.rstrip().rstrip(","))
            line = token
        else:
            line += token
    if line.strip():
        lines.append(line.rstrip().rstrip(","))
    return "\n".join(lines)


def build_extraction_prompt(state: str, species: str, year: int, unit_codes: List[str]) -> str:
    """
    Build instructions the LLM will follow to output structured JSON.

    Key requirement for this iteration:
    - The output MUST include a "units" entry for EVERY unit_code provided.
    - If there are no special seasons/restrictions found for a unit, include that unit
      with empty arrays (do NOT omit the unit).
    """
    unit_codes_norm = [str(u).strip() for u in unit_codes if str(u).strip()]
    unit_list_block = _format_unit_list(unit_codes_norm)

    # Pure text (NOT an f-string). Keep it JSON-like but avoid comment syntax like //,
    # because models sometimes copy that and return invalid JSON.
    schema_example = r"""
{
  "state": "<full state name>",
  "year": <int>,
  "species": "<species name, e.g., elk>",
  "units": [
    {
      "unit_code": "310",
      "unit_name": "Upper Gallatin",
      "seasons": [],
      "unit_restrictions": []
    },
    {
      "unit_code": "320",
      "seasons": [
        {
          "weapon": "archery",
          "season_type": "archery",
          "start_date": "2025-09-06",
          "end_date": "2025-10-19",
          "licenses_required": [
            {
              "code": "General Elk",
              "residency": "either"
            }
          ],
          "restrictions": [
            {
              "type": "antler",
              "summary": "Brow-tined bull only.",
              "details": "Only valid in the specified sub-area..."
            }
          ],
          "source": {
            "document_name": "2025-deer-elk-antelope-regulations-final-for-web.pdf",
            "page_number": 72
          }
        }
      ],
      "unit_restrictions": [
        {
          "type": "land_access",
          "summary": "Area closed except by special permit.",
          "details": "Short details...",
          "source": {
            "document_name": "2025-deer-elk-antelope-regulations-final-for-web.pdf",
            "page_number": 72
          }
        }
      ]
    }
  ],
  "statewide_restrictions": [
    {
      "type": "blaze_orange",
      "summary": "Blaze orange required during general firearms seasons.",
      "details": "Hunters must wear at least 400 square inches of hunter orange.",
      "source": {
        "document_name": "2025-deer-elk-antelope-regulations-final-for-web.pdf",
        "page_number": 3
      }
    }
  ]
}
""".strip()

    prompt = f"""
You are extracting hunting regulations into STRICT JSON.

Task:
- Extract hunting regulation facts for state={state}, species={species}, year={year}.
- Use ONLY the attached regulation documents (via file_search). Do not guess.
- If you cannot confirm a fact, omit that fact (but still include required unit shells).

CRITICAL REQUIREMENT (Units):
- You MUST include one "units" entry for EVERY unit_code in the authoritative list below.
- Do NOT omit any unit_code from the list.
- If you cannot find any special seasons or restrictions for a unit, include that unit with:
  - "seasons": []
  - "unit_restrictions": []
- Each unit_code must appear EXACTLY ONCE in the output "units" array.

Authoritative unit codes to include (count={len(unit_codes_norm)}):
{unit_list_block}

Output:
- Return EXACTLY ONE JSON object matching the schema below.
- JSON ONLY: no markdown, no code fences, no comments, no extra text before/after JSON.

Schema example (structure + field names):
{schema_example}

Normalization rules:
- Dates MUST be "YYYY-MM-DD".
- weapon MUST be one of: archery, rifle, muzzleloader, shotgun, handgun, any_legal_weapon, unknown
- residency MUST be one of: resident, nonresident, either, unknown
- restriction.type SHOULD be one of: antler, blaze_orange, vehicle_access, land_access, weapon_specific, youth_only, permit_required, other

Quality rules:
- Keep "details" short (a few sentences max).
- Include "source.page_number" ONLY if you are confident; otherwise omit page_number.
""".strip()

    return prompt

# --------------------------------------------------------------------
# 3. Call the LLM with file_search
# --------------------------------------------------------------------

def call_extraction_llm(state: str, species: str, year: int) -> Tuple[str, List[str]]:
    """
    Use the Responses API + file_search to extract structured JSON.
    Returns (raw_text, unit_codes_used).
    """
    cfg, client, vs = _get_client_and_vector_store()
    file_search_tool = _build_file_search_tool(state, species, vs)

    # Pull authoritative unit list from regulations.toml
    unit_codes = cfg.units_for(state, species)  # e.g., ["310", "312", ...]
    prompt = build_extraction_prompt(state, species, year, unit_codes)

    response = client.responses.create(
        model=cfg.model_name,
        input=prompt,
        tools=[file_search_tool],
        temperature=0,
    )

    return response.output_text, [str(u).strip() for u in unit_codes if str(u).strip()]

# --------------------------------------------------------------------
# 4. Parse + basic validation
# --------------------------------------------------------------------

def _normalize_unit_code(x: Any) -> str:
    return str(x).strip()


def _ensure_all_units_present(data: Dict[str, Any], unit_codes: List[str]) -> Dict[str, Any]:
    """
    Ensure every unit_code exists exactly once in data["units"].

    Strategy:
    - If the model omitted units, we add "shell" units with empty arrays.
    - If the model duplicated a unit_code, we keep the first and drop later duplicates.
    """
    expected = [_normalize_unit_code(u) for u in unit_codes if _normalize_unit_code(u)]
    expected_set = set(expected)

    units = data.get("units", [])
    if not isinstance(units, list):
        units = []

    seen = set()
    normalized_units = []
    for u in units:
        if not isinstance(u, dict):
            continue
        code = _normalize_unit_code(u.get("unit_code", ""))
        if not code or code not in expected_set:
            # ignore unknown unit codes; you can change this to keep them if desired
            continue
        if code in seen:
            continue
        seen.add(code)
        # ensure required arrays exist
        u.setdefault("seasons", [])
        u.setdefault("unit_restrictions", [])
        normalized_units.append(u)

    # Add missing shells
    missing = [c for c in expected if c not in seen]
    for code in missing:
        normalized_units.append({
            "unit_code": code,
            "seasons": [],
            "unit_restrictions": []
        })

    # Sort by unit_code for stable output (numeric sort when possible)
    def _sort_key(u: Dict[str, Any]):
        code = _normalize_unit_code(u.get("unit_code", ""))
        try:
            return (0, int(code))
        except Exception:
            return (1, code)

    normalized_units.sort(key=_sort_key)
    data["units"] = normalized_units
    return data


def parse_and_validate_json(raw_text: str, state: str, species: str, year: int, unit_codes: List[str]) -> Dict[str, Any]:
    """
    Parse model output as JSON and perform basic sanity checks.

    Also enforces that ALL expected units are present (adding empty shells if needed).
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Model output was not valid JSON: {e}\n\n"
            f"Raw (first 800 chars):\n{raw_text[:800]}"
        )

    # Sanity checks (keep relatively lightweight)
    extracted_species = (data.get("species") or "").strip().lower()
    if extracted_species and extracted_species != species.strip().lower():
        raise ValueError(f"Extracted species '{data.get('species')}' != expected '{species}'")

    if "year" in data:
        try:
            if int(data["year"]) != int(year):
                raise ValueError(f"Extracted year '{data['year']}' != expected '{year}'")
        except Exception as e:
            raise ValueError(f"Invalid 'year' field in extracted JSON: {e}")

    # Validate dates if present
    for unit in data.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        for season in unit.get("seasons", []) or []:
            if not isinstance(season, dict):
                continue
            for key in ("start_date", "end_date"):
                if key in season and season[key]:
                    try:
                        datetime.strptime(season[key], "%Y-%m-%d")
                    except Exception as e:
                        raise ValueError(f"Invalid date '{season[key]}' in season: {e}")

    # Enforce unit coverage (fills missing unit shells + dedupes)
    data = _ensure_all_units_present(data, unit_codes)

    # Final assert: guarantee coverage
    out_codes = {_normalize_unit_code(u.get("unit_code", "")) for u in (data.get("units") or []) if isinstance(u, dict)}
    missing = [c for c in unit_codes if _normalize_unit_code(c) and _normalize_unit_code(c) not in out_codes]
    if missing:
        raise ValueError(f"After normalization, still missing unit_code(s): {missing[:20]}{'...' if len(missing) > 20 else ''}")

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
    raw, unit_codes = call_extraction_llm(state, species, year)
    data = parse_and_validate_json(raw, state, species, year, unit_codes)

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
    state = "Montana"
    species = "elk"
    year = 2025

    path = extract_reg_graph(state, species, year)
    print(f"Wrote structured regulations JSON to: {path}")
