import os
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

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

def _chunk_list(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


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


def build_extraction_prompt(state: str, species: str, year: int, unit_codes_batch: List[str]) -> str:
    """
    Build instructions the LLM will follow to output structured JSON for ONE BATCH of unit codes.

    Why batching:
    - Listing 150+ units in a single prompt tends to push the model into "compliance mode"
      (it outputs empty shells) and leaves less room for retrieved evidence.
    - Smaller batches help retrieval focus and usually yield more populated seasons/restrictions.
    """
    unit_codes_norm = [str(u).strip() for u in unit_codes_batch if str(u).strip()]
    unit_list_block = _format_unit_list(unit_codes_norm)

    # JSON example as plain string (NOT f-string) to avoid brace parsing issues.
    schema_example = r"""
{
  "state": "<full state name>",
  "year": <int>,
  "species": "<species name>",
  "units": [
    {
      "unit_code": "310",
      "unit_name": "Upper Gallatin",
      "seasons": [
        {
          "weapon": "archery",
          "season_type": "archery",
          "start_date": "2025-09-06",
          "end_date": "2025-10-19",
          "licenses_required": [
            { "code": "General Elk", "residency": "either" }
          ],
          "restrictions": [
            { "type": "antler", "summary": "Brow-tined bull only.", "details": "..." }
          ],
          "source": { "document_name": "regulations.pdf", "page_number": 72 }
        }
      ],
      "unit_restrictions": [
        {
          "type": "land_access",
          "summary": "Area closed except by special permit.",
          "details": "...",
          "source": { "document_name": "regulations.pdf", "page_number": 72 }
        }
      ]
    },
    {
      "unit_code": "312",
      "seasons": [],
      "unit_restrictions": []
    }
  ],
  "statewide_restrictions": [
    {
      "type": "blaze_orange",
      "summary": "Blaze orange required during general firearms seasons.",
      "details": "Hunters must wear at least 400 square inches of hunter orange.",
      "source": { "document_name": "general.pdf", "page_number": 3 }
    }
  ]
}
""".strip()

    # A small retrieval hint list. This nudges the model to search for unit-specific pages/tables.
    # The model will decide when to call file_search, but these terms help guide what to look for.
    hint_terms = ", ".join([f"HD {u}" for u in unit_codes_norm[:10]])  # cap so it's not huge

    prompt = f"""
You are extracting hunting regulations into STRICT JSON.

Task:
- Extract hunting regulation facts for state={state}, species={species}, year={year}.
- Use ONLY the attached regulation documents (via file_search). Do not guess.
- Focus ONLY on the unit codes listed below (this is one batch of units).
- If you cannot confirm a specific season/restriction/license detail, omit that detail.

CRITICAL REQUIREMENT (Units for this batch):
- You MUST include one "units" entry for EVERY unit_code in the list below.
- Each unit_code must appear EXACTLY ONCE in the output "units" array.
- If you cannot find any special seasons or restrictions for a unit, include that unit with:
  - "seasons": []
  - "unit_restrictions": []

Unit codes in this batch (count={len(unit_codes_norm)}):
{unit_list_block}

Retrieval hints (use file_search to find relevant tables/sections mentioning these units):
{hint_terms}

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
# 3. Model call (batched) + merge
# --------------------------------------------------------------------

def _normalize_unit_code(x: Any) -> str:
    return str(x).strip()


def _merge_unit(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two unit dicts, preferring richer (non-empty) seasons/restrictions.
    """
    out = dict(existing)

    # unit_name: keep incoming if existing missing
    if not out.get("unit_name") and incoming.get("unit_name"):
        out["unit_name"] = incoming["unit_name"]

    # seasons: prefer incoming if it has content and existing is empty
    out.setdefault("seasons", [])
    out.setdefault("unit_restrictions", [])

    inc_seasons = incoming.get("seasons") or []
    inc_restr = incoming.get("unit_restrictions") or []

    if inc_seasons and not out["seasons"]:
        out["seasons"] = inc_seasons
    elif inc_seasons and out["seasons"]:
        # naive append-dedup by (weapon, season_type, start_date, end_date)
        seen = {(s.get("weapon"), s.get("season_type"), s.get("start_date"), s.get("end_date")) for s in out["seasons"] if isinstance(s, dict)}
        for s in inc_seasons:
            if not isinstance(s, dict):
                continue
            key = (s.get("weapon"), s.get("season_type"), s.get("start_date"), s.get("end_date"))
            if key not in seen:
                out["seasons"].append(s)
                seen.add(key)

    if inc_restr and not out["unit_restrictions"]:
        out["unit_restrictions"] = inc_restr
    elif inc_restr and out["unit_restrictions"]:
        seen = {(r.get("type"), r.get("summary")) for r in out["unit_restrictions"] if isinstance(r, dict)}
        for r in inc_restr:
            if not isinstance(r, dict):
                continue
            key = (r.get("type"), r.get("summary"))
            if key not in seen:
                out["unit_restrictions"].append(r)
                seen.add(key)

    return out


def _merge_outputs(base: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge partial extraction output into base output.
    """
    # Merge statewide restrictions (dedup by type+summary)
    base.setdefault("statewide_restrictions", [])
    part_restr = part.get("statewide_restrictions") or []
    if part_restr:
        seen = {(r.get("type"), r.get("summary")) for r in base["statewide_restrictions"] if isinstance(r, dict)}
        for r in part_restr:
            if not isinstance(r, dict):
                continue
            key = (r.get("type"), r.get("summary"))
            if key not in seen:
                base["statewide_restrictions"].append(r)
                seen.add(key)

    # Merge units by unit_code
    base.setdefault("units", [])
    by_code: Dict[str, Dict[str, Any]] = {}
    for u in base["units"]:
        if isinstance(u, dict):
            code = _normalize_unit_code(u.get("unit_code", ""))
            if code:
                by_code[code] = u

    for u in (part.get("units") or []):
        if not isinstance(u, dict):
            continue
        code = _normalize_unit_code(u.get("unit_code", ""))
        if not code:
            continue
        if code in by_code:
            by_code[code] = _merge_unit(by_code[code], u)
        else:
            u.setdefault("seasons", [])
            u.setdefault("unit_restrictions", [])
            by_code[code] = u

    base["units"] = list(by_code.values())
    return base


def _ensure_all_units_present(data: Dict[str, Any], unit_codes: List[str]) -> Dict[str, Any]:
    """
    Ensure every unit_code exists exactly once in data["units"].
    Adds missing shell units with empty arrays.
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
            continue
        if code in seen:
            continue
        seen.add(code)
        u.setdefault("seasons", [])
        u.setdefault("unit_restrictions", [])
        normalized_units.append(u)

    missing = [c for c in expected if c not in seen]
    for code in missing:
        normalized_units.append({"unit_code": code, "seasons": [], "unit_restrictions": []})

    def _sort_key(u: Dict[str, Any]):
        code = _normalize_unit_code(u.get("unit_code", ""))
        try:
            return (0, int(code))
        except Exception:
            return (1, code)

    normalized_units.sort(key=_sort_key)
    data["units"] = normalized_units
    return data


def _parse_json(raw_text: str) -> Dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned empty output")

    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # remove opening fence (``` or ```json)
        text = text.split("```", 1)[1]
        # remove closing fence if present
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    # Fallback: extract first {...} block
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Model output was not valid JSON: {e}\n\n"
            f"Raw (first 800 chars):\n{raw_text[:800]}"
        )



def _validate_dates(data: Dict[str, Any]) -> None:
    for unit in data.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        for season in unit.get("seasons", []) or []:
            if not isinstance(season, dict):
                continue
            for key in ("start_date", "end_date"):
                if key in season and season[key]:
                    datetime.strptime(season[key], "%Y-%m-%d")


def call_extraction_llm_batched(state: str, species: str, year: int, batch_size: int = 30) -> Tuple[Dict[str, Any], List[str]]:
    """
    Run extraction in batches of unit codes, then merge outputs.
    Returns (merged_data, unit_codes_used).
    """
    cfg, client, vs = _get_client_and_vector_store()
    file_search_tool = _build_file_search_tool(state, species, vs)

    unit_codes_all = [str(u).strip() for u in (cfg.units_for(state, species) or []) if str(u).strip()]
    batches = _chunk_list(unit_codes_all, batch_size)

    merged: Dict[str, Any] = {
        "state": state,
        "year": year,
        "species": species,
        "units": [],
        "statewide_restrictions": [],
    }

    for batch in batches:
        prompt = build_extraction_prompt(state, species, year, batch)

        resp = client.responses.create(
            model=cfg.model_name,
            input=prompt,
            tools=[file_search_tool],
            temperature=0,
        )

        print("\n" + "=" * 80)
        print("LLM RAW RESPONSE (batch):")
        print(resp.output_text)
        print("=" * 80 + "\n")

        part = _parse_json(resp.output_text)

        # lightweight checks
        _validate_dates(part)

        merged = _merge_outputs(merged, part)

    # Ensure full unit coverage (shell-fill any remaining)
    merged = _ensure_all_units_present(merged, unit_codes_all)

    return merged, unit_codes_all

# --------------------------------------------------------------------
# 4. Orchestration: run extraction + write to file
# --------------------------------------------------------------------

def extract_reg_graph(state: str, species: str, year: int, output_dir: str = "output/graph", batch_size: int = 30) -> str:
    """
    High-level entrypoint:
    - Calls the LLM with file_search in unit batches
    - Merges partial outputs
    - Ensures all unit shells exist
    - Writes JSON to output_dir as <state>_<species>_<year>.json
    """
    data, unit_codes = call_extraction_llm_batched(state, species, year, batch_size=batch_size)

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{state.lower()}_{species.lower()}_{year}.json".replace(" ", "_")
    out_path = os.path.join(output_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return out_path

# --------------------------------------------------------------------
# 5. Simple CLI runner
# --------------------------------------------------------------------

if __name__ == "__main__":
    state = "Montana"
    species = "elk"
    year = 2025

    # Tip: start with 25-40. Smaller batches usually populate more unit detail.
    path = extract_reg_graph(state, species, year, batch_size=30)
    print(f"Wrote structured regulations JSON to: {path}")
