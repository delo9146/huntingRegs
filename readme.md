# Hunting Regulations POC

This proof-of-concept (POC) demonstrates automated ingestion of U.S. state hunting regulation PDFs into an OpenAI-powered vector store. It supports both:

- **Web Ingestion**: Fetches the latest PDFs directly from state wildlife agency websites, saves them locally, and uploads them into a dedicated vector store (`regs-store-web`).
- **Batch Ingestion**: Takes PDFs already present in the `data/input/` folder and indexes them into any configured vector store with species- and state-based metadata.

---

## 🔧 Prerequisites

- Python 3.9+
- An OpenAI API key with Files API and Vector Store access
- `regulations.toml` in project root, configured with your environment:
  ```toml
  [vector_store]
  vector_store_web = "regs-store-web"

  [api]
  api_key_env = "OPENAI_API_KEY"

  [ingest]
  input_dir = "data/input"
  output_dir = "data/output"
  valid_species = ["deer", "elk", "antelope", "black-bear", ...]
  sources_by_state = { montana = "https://fwp.mt.gov/...", colorado = "https://cpw.state.co.us/..." }
  ```

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export your OpenAI key:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

---

## 🏗️ Project Structure

```
├── assistantManager.py    # OpenAI Files + Vector Store wrapper
├── configManager.py       # Loads regulations.toml into cfg properties
├── sourceManager.py       # Downloads PDFs from web, normalizes names, fires ingest hooks
├── ingest_web.py          # Orchestrates web ingestion + vector upload
├── ingest.py              # (Optional) Batch ingest local PDFs into vector store
├── data/                  # Local PDFs and outputs
│   ├── input/             # state subfolders of downloaded PDFs
│   └── output/            # generated outputs (if used)
├── app.py                 # (Optional) Streamlit UI entrypoint
├── appManager.py          # (Optional) UI logic for summaries & demos
└── query_helper.py        # (Optional) UI query helper functions
```

---

## 🚀 Running the Web Ingest

This is the recommended, "always-on" pipeline to fetch and index new regs:

```bash
python ingest_web.py
```

**What happens:**

1. Loads config from `regulations.toml`.
2. Creates or opens vector store named by `vector_store_web`.
3. Iterates each state in `cfg.sources_by_state`:
   - Fetches hub page, scrapes PDF URLs.
   - Downloads PDFs into `data/input/<state>/` (skips unchanged files).
   - On each successful download, calls `AssistantManager.ingest_file(...)` to:
     - Upload PDF to OpenAI Files API (if not already present).
     - Attach it to the vector store with metadata:
       ```json
       {
         "state": "<state>",
         "<species1>": true,
         "<species2>": true
       }
       ```
     - Chunks at 800 tokens with 400-token overlap.

Logs show HTTP calls, retry behavior, and overall success for each file.

---

## 🗂️ Batch Ingest (Optional)

If you already have local PDFs and want to index them in bulk:

```bash
python ingest.py
```

**What happens:**

- Walks `data/input/` for all state subfolders.
- Extracts species from filenames via `extract_species_from_filename`.
- Uploads and indexes each PDF exactly as the web pipeline.

---

## 🧹 Cleanup & Simplification

- **Removed** `fileManager.py`: `sourceManager.py` now reads `cfg.input_dir` & `cfg.output_dir` directly.
- **Pruned** unused prompt templates, helper methods, and UI modules not required for ingestion.
- **Audit** your config file to remove any states or species you no longer need.

---

## 🔄 Extending or Modifying

- To add a new state, update `cfg.sources_by_state` in `regulations.toml` and provide a `_fetch_<state>_rules()` method in `sourceManager.py` following the Colorado/Montana pattern.
- To change chunk size or overlap, modify the static chunk settings in `assistantManager.py`.
- To tag additional metadata (e.g., year, document type), enhance `ingest_file()` to include new `metadata[...] = ...` entries.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Submit a PR with tests or a short demo

---

*Enjoy searching through regulations with the power of LLMs!*

