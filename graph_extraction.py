import os
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from openai import OpenAI
from configManager import ConfigManager
from ingestManager import IngestManager

# --------------------------------------------------------------------
# 0. Lightweight timing / logging helpers
# --------------------------------------------------------------------

class StepTimer:
    """
    Simple timer that tracks named steps and prints durations to stdout.
    """
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.steps: List[Tuple[str, float]] = []

    def mark(self, name: str) -> None:
        now = time.perf_counter()
        elapsed = now - (self._t0 if not self.steps else (self._t0 + sum(s[1] for s in self.steps)))
        self.steps.append((name, elapsed))

    def total(self) -> float:
        return time.perf_counter() - self._t0

    def summary_lines(self, prefix: str = "") -> List[str]:
        lines = []
        for name, secs in self.steps:
            lines.append(f"{prefix}{name}: {secs:.2f}s")
        lines.append(f"{prefix}TOTAL: {self.total():.2f}s")
        return lines


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# --------------------------------------------------------------------
# 1. Setup helpers: client + vector store
# --------------------------------------------------------------------

def _get_client_and_vector_store() -> Tuple[ConfigManager, OpenAI, Any]:
    """
    Initialize OpenAI client and get/create the regulations vector store.
    """
    cfg = ConfigManager()
    im = IngestManager(cfg)
    vs = im.get_or_create_vector_store(cfg.vector_store_name)
    client = OpenAI(api_key=os.getenv(cfg.api_key_env))
    return cfg, client, vs


def _build_filters(state: str, species: str) -> Dict[str, Any]:
    """
    Filters matching your ingestion attributes.
    """
    return {
        "type": "and",
        "filters": [
            {"type": "eq", "key": "state", "value": state.lower()},
            {"type": "eq", "key": species, "value": True},
        ],
    }

# --------------------------------------------------------------------
# 2. Prompt construction
# --------------------------------------------------------------------

def _chunk_list(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _format_unit_list(unit_codes: List[str], max_line_len: int = 110) -> str:
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


def build_extraction_prompt(state: str, species: str, year: int, unit_codes_batch: List[str], evidence_block: str) -> str:
    """
    Build instructions the LLM will follow to output structured JSON for ONE BATCH of unit codes.

    In this version, we DO NOT rely on model-driven file_search. Instead, we:
      1) Programmatically retrieve evidence snippets from the vector store per HD
      2) Feed those snippets to the model in an EVIDENCE block
      3) Ask the model to output structured JSON
    """
    unit_codes_norm = [str(u).strip() for u in unit_codes_batch if str(u).strip()]
    unit_list_block = _format_unit_list(unit_codes_norm)

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
          "source": { "document_name": "2025-deer-elk-antelope-regulations-final-for-web.pdf", "page_number": 72 }
        }
      ],
      "unit_restrictions": [
        {
          "type": "land_access",
          "summary": "Area closed except by special permit.",
          "details": "...",
          "source": { "document_name": "2025-deer-elk-antelope-regulations-final-for-web.pdf", "page_number": 72 }
        }
      ]
    },
    {
      "unit_code": "312",
      "seasons": [],
      "unit_restrictions": []
    }
  ],
  "statewide_restrictions": []
}
""".strip()

    prompt = f"""
You are extracting hunting regulations into STRICT JSON.

Task:
- Extract hunting regulation facts for state={state}, species={species}, year={year}.
- Use ONLY the EVIDENCE SNIPPETS below. Do not guess. Do not invent units.
- Focus ONLY on the unit codes listed below (this is one batch of units).
- If you cannot confirm a specific season/restriction/license detail from evidence, omit that detail.

CRITICAL REQUIREMENT (Units for this batch):
- You MUST include one "units" entry for EVERY unit_code in the list below.
- Each unit_code must appear EXACTLY ONCE in the output "units" array.
- If you cannot find any seasons or restrictions for a unit in the evidence, include that unit with:
  - "seasons": []
  - "unit_restrictions": []

Unit codes in this batch (count={len(unit_codes_norm)}):
{unit_list_block}

EVIDENCE SNIPPETS (retrieved per-HD from the regulations vector store):
{evidence_block}

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
- Include "source.document_name" whenever possible if the evidence provides it; include page_number only if present in evidence.
""".strip()

    return prompt

# --------------------------------------------------------------------
# 3. Parsing + validation
# --------------------------------------------------------------------

def _parse_json(raw_text: str) -> Dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned empty output")

    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```", 1)[1]
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


def _normalize_unit_code(x: Any) -> str:
    return str(x).strip()


def _ensure_all_units_present(data: Dict[str, Any], unit_codes: List[str]) -> Dict[str, Any]:
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

# --------------------------------------------------------------------
# 4. Programmatic retrieval: query vector store per HD
# --------------------------------------------------------------------

def _extract_text_from_vs_result(r: Any) -> str:
    content = getattr(r, "content", None)
    if content is None and isinstance(r, dict):
        content = r.get("content")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text", "")
                if t and t.strip():
                    texts.append(t.strip())
            elif isinstance(part, str) and part.strip():
                texts.append(part.strip())
        return "\n".join(texts).strip()

    return ""


def _extract_source_hint(r: Any) -> str:
    file_name = getattr(r, "file_name", None) or getattr(r, "filename", None)
    if file_name is None and isinstance(r, dict):
        file_name = r.get("file_name") or r.get("filename")

    page = getattr(r, "page_number", None)
    if page is None and isinstance(r, dict):
        page = r.get("page_number")

    bits = []
    if file_name:
        bits.append(str(file_name))
    if page is not None:
        bits.append(f"p.{page}")
    return " | ".join(bits)


def _safe_vector_store_search(
    client: OpenAI,
    vs_id: str,
    query: str,
    filters: Dict[str, Any],
    max_num_results: int,
) -> Any:
    """
    Wrapper around vector store search for best-practice error handling.
    """
    try:
        return client.vector_stores.search(
            vector_store_id=vs_id,
            query=query,
            filters=filters,
            max_num_results=max_num_results,
        )
    except Exception as e:
        # Keep running; evidence will just be missing for this unit.
        print(f"[WARN] vector_stores.search failed for query='{query}': {type(e).__name__}: {e}")
        return None


def retrieve_evidence_for_batch(
    client: OpenAI,
    vs_id: str,
    state: str,
    species: str,
    unit_codes_batch: List[str],
    per_unit_results: int = 2,
    max_chars: int = 12000
) -> str:
    """
    Programmatically query the vector store for each HD in the batch and stitch
    the results into an evidence block.

    This replaces model-driven file_search for coverage-oriented extraction.
    """
    filters = _build_filters(state, species)
    chunks: List[str] = []
    used = 0

    for code in unit_codes_batch:
        q = f'HD {code} elk hunting district {code} regulations restrictions seasons'
        res = _safe_vector_store_search(
            client=client,
            vs_id=vs_id,
            query=q,
            filters=filters,
            max_num_results=per_unit_results,
        )
        if res is None:
            continue

        results = getattr(res, "data", None) or getattr(res, "results", None) or []
        print(f"[DEBUG] HD {code}: hits={len(results)}")
        print(results)
        if not results:
            continue

        snippet_texts = []
        for r in results:
            txt = _extract_text_from_vs_result(r)
            if not txt:
                continue
            src = _extract_source_hint(r)
            if src:
                snippet_texts.append(f"[{src}]\n{txt}")
            else:
                snippet_texts.append(txt)
            if results:
              # Only for the first result, once per HD, print content shape
              r0 = results[0]
              print(f"[DEBUG] HD {code}: first result type={type(r0)}")
              if isinstance(r0, dict):
                  print(f"[DEBUG] HD {code}: first result dict keys={list(r0.keys())[:20]}")
              else:
                  # show some likely fields
                  for attr in ("content", "text", "chunk", "document", "metadata"):
                      if hasattr(r0, attr):
                          v = getattr(r0, attr)
                          print(f"[DEBUG] HD {code}: attr {attr} type={type(v)}")
                          break


        if not snippet_texts:
            continue

        block = f"\n### HD {code}\n" + "\n---\n".join(snippet_texts)
        if used + len(block) > max_chars:
            break
        chunks.append(block)
        used += len(block)

    if not chunks:
        return "(No evidence retrieved from vector store for this batch.)"

    return "\n".join(chunks).strip()

# --------------------------------------------------------------------
# 5. Merge helpers (unchanged)
# --------------------------------------------------------------------

def _merge_unit(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(existing)

    if not out.get("unit_name") and incoming.get("unit_name"):
        out["unit_name"] = incoming["unit_name"]

    out.setdefault("seasons", [])
    out.setdefault("unit_restrictions", [])

    inc_seasons = incoming.get("seasons") or []
    inc_restr = incoming.get("unit_restrictions") or []

    if inc_seasons and not out["seasons"]:
        out["seasons"] = inc_seasons
    elif inc_seasons and out["seasons"]:
        seen = {(s.get("weapon"), s.get("season_type"), s.get("start_date"), s.get("end_date"))
                for s in out["seasons"] if isinstance(s, dict)}
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
    base.setdefault("statewide_restrictions", [])
    base.setdefault("units", [])

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

# --------------------------------------------------------------------
# 6. Main extraction (batched): retrieve evidence -> LLM -> merge
# --------------------------------------------------------------------

def _safe_llm_call(client: OpenAI, model: str, prompt: str) -> Optional[str]:
    """
    Wrapper around the LLM call for best-practice error handling.
    Returns output_text or None.
    """
    try:
        resp = client.responses.create(
            model=model,
            input=prompt,
            temperature=0,
        )
        return getattr(resp, "output_text", None) or ""
    except Exception as e:
        print(f"[WARN] LLM call failed: {type(e).__name__}: {e}")
        return None


def call_extraction_llm_batched(
    state: str,
    species: str,
    year: int,
    batch_size: int = 30,
    per_unit_results: int = 2
) -> Tuple[Dict[str, Any], List[str]]:
    cfg, client, vs = _get_client_and_vector_store()

    unit_codes_all = [str(u).strip() for u in (cfg.units_for(state, species) or []) if str(u).strip()]
    batches = _chunk_list(unit_codes_all, batch_size)

    merged: Dict[str, Any] = {
        "state": state,
        "year": year,
        "species": species,
        "units": [],
        "statewide_restrictions": [],
    }

    _print_header("GRAPH EXTRACTION RUN START")
    print(f"State={state} | Species={species} | Year={year}")
    print(f"Total units: {len(unit_codes_all)} | Batch size: {batch_size} | Batches: {len(batches)}")
    print(f"Vector store id: {getattr(vs, 'id', 'unknown')}")

    # SANITY CHECK: can we retrieve anything from the vector store at all?
    try:
        sanity = client.vector_stores.search(
            vector_store_id=vs.id,
            query="elk season",
            max_num_results=5,
        )
        sanity_results = getattr(sanity, "data", None) or getattr(sanity, "results", None) or []
        print(f"[SANITY] vector store search results for 'elk season': {len(sanity_results)}")
        if sanity_results:
            print(f"[SANITY] first result type: {type(sanity_results[0])}")
            print(f"[SANITY] first result keys/attrs: {dir(sanity_results[0])[:25]}")
    except Exception as e:
        print(f"[SANITY] vector store search failed: {type(e).__name__}: {e}")


    total_timer = StepTimer()

    for i, batch in enumerate(batches, start=1):
        batch_timer = StepTimer()
        _print_header(f"Batch {i}/{len(batches)} | HDs {batch[0]}..{batch[-1]} (count={len(batch)})")

        # Step 1: Query vector store and build evidence
        try:
            evidence = retrieve_evidence_for_batch(
                client=client,
                vs_id=vs.id,
                state=state,
                species=species,
                unit_codes_batch=batch,
                per_unit_results=per_unit_results,
            )
        except Exception as e:
            evidence = "(Error retrieving evidence for this batch.)"
            print(f"[WARN] Evidence retrieval failed for batch {i}: {type(e).__name__}: {e}")
        batch_timer.mark("Query vector store (build evidence)")
        os.makedirs("output/evidence", exist_ok=True)
        with open(f"output/evidence/batch_{i:02d}_evidence.txt", "w", encoding="utf-8") as f:
            f.write(evidence)
        print(f"[INFO] Wrote evidence for batch {i} to output/evidence/batch_{i:02d}_evidence.txt")
        print(f"[INFO] Evidence length (chars): {len(evidence)}")

        # Step 2: Build prompt
        try:
            prompt = build_extraction_prompt(state, species, year, batch, evidence)
        except Exception as e:
            print(f"[ERROR] Prompt build failed for batch {i}: {type(e).__name__}: {e}")
            # Skip batch; continue processing remaining batches
            continue
        batch_timer.mark("Build prompt")

        # Step 3: Call LLM
        output_text = _safe_llm_call(client=client, model=cfg.model_name, prompt=prompt)
        batch_timer.mark("LLM call (send evidence + get JSON)")

        if output_text is None:
            print(f"[WARN] Skipping batch {i} due to LLM failure.")
            print("\n".join(batch_timer.summary_lines(prefix="  ")))
            continue

        # Step 4: Parse + validate + merge
        try:
            part = _parse_json(output_text)
            _validate_dates(part)
            merged = _merge_outputs(merged, part)
        except Exception as e:
            print(f"[WARN] Parse/validate/merge failed for batch {i}: {type(e).__name__}: {e}")
        batch_timer.mark("Parse + validate + merge")

        print("\n".join(batch_timer.summary_lines(prefix="  ")))

    # Finalize: ensure all units exist
    try:
        merged = _ensure_all_units_present(merged, unit_codes_all)
    except Exception as e:
        print(f"[WARN] ensure_all_units_present failed: {type(e).__name__}: {e}")
    total_timer.mark("Finalize (ensure all units present)")

    print("\n" + "-" * 80)
    print("RUN SUMMARY")
    print("-" * 80)
    print("\n".join(total_timer.summary_lines(prefix="  ")))
    return merged, unit_codes_all

# --------------------------------------------------------------------
# 7. Orchestration
# --------------------------------------------------------------------

def extract_reg_graph(
    state: str,
    species: str,
    year: int,
    output_dir: str = "output/graph",
    batch_size: int = 30,
    per_unit_results: int = 2
) -> str:
    run_timer = StepTimer()

    data, _ = call_extraction_llm_batched(
        state=state,
        species=species,
        year=year,
        batch_size=batch_size,
        per_unit_results=per_unit_results,
    )
    run_timer.mark("Extraction (all batches)")

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{state.lower()}_{species.lower()}_{year}.json".replace(" ", "_")
    out_path = os.path.join(output_dir, filename)

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise RuntimeError(f"Failed writing output JSON to '{out_path}': {type(e).__name__}: {e}") from e

    run_timer.mark("Write JSON to disk")

    _print_header("GRAPH EXTRACTION COMPLETE")
    print(f"Output JSON: {out_path}")
    print("\n".join(run_timer.summary_lines(prefix="  ")))
    return out_path

# --------------------------------------------------------------------
# 8. CLI runner
# --------------------------------------------------------------------

if __name__ == "__main__":
    state = "Montana"
    species = "elk"
    year = 2025

    # batch_size: smaller batches can increase per-unit population
    # per_unit_results: top-k snippets pulled per HD from vector store
    path = extract_reg_graph(state, species, year, batch_size=30, per_unit_results=2)
    print(f"Wrote structured regulations JSON to: {path}")
