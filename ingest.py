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

    state_pdfs = get_all_state_pdfs(cfg.input_dir)
    for state_folder, pdf_path in state_pdfs:
        print(f"Ingesting {pdf_path} for state {state_folder}")
        am.ingest_file(pdf_path, state=state_folder)

    am.update_assistant()
    print("Assistant updated with all ingested documents.")



def get_all_state_pdfs(input_dir):
    state_pdfs = []
    for state_folder in os.listdir(input_dir):
        state_path = os.path.join(input_dir, state_folder)
        if not os.path.isdir(state_path):
            continue
        for fname in os.listdir(state_path):
            if fname.lower().endswith(".pdf"):
                pdf_path = os.path.join(state_path, fname)
                state_pdfs.append((state_folder, pdf_path))
    return state_pdfs


if __name__ == "__main__":
    run_ingest()
