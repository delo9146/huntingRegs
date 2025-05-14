import os
from configManager    import ConfigManager
from fileManager      import FileManager
from assistantManager import AssistantManager

def run_ingest():
    cfg = ConfigManager()

    fm = FileManager(cfg.input_dir, cfg.output_dir)
    am = AssistantManager(cfg)

    vs = am.get_or_create_vector_store()
    print(f"Vector store ready (id={vs.id})")

    assistant = am.get_or_create_assistant(cfg.assistant_name)
    print(f"Assistant ready (id={assistant.id})")

    for fname in os.listdir(cfg.input_dir):
        if not fname.lower().endswith(".pdf"):
            continue

        path = fm.get_input_path(fname)
        print(f"Ingesting {fname}…")
        am.ingest_file(path)

    am.update_assistant()
    print("Assistant updated with all ingested documents.")

if __name__ == "__main__":
    run_ingest()
