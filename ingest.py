import os
import re
from configManager import ConfigManager
from fileManager import FileManager
from assistantManager import AssistantManager

def run_ingest():
    cfg = ConfigManager()
    valid_species = cfg.valid_species

    fm = FileManager(cfg.input_dir, cfg.output_dir)
    am = AssistantManager(cfg)

    vs = am.get_or_create_vector_store()
    print(f"Vector store ready (id={vs.id})")

    assistant = am.get_or_create_assistant(cfg.assistant_name)
    print(f"Assistant ready (id={assistant.id})")

    state_pdfs = get_all_state_pdfs(cfg.input_dir)
    for state_folder, pdf_path in state_pdfs:
        species = extract_species_from_filename(os.path.basename(pdf_path), valid_species)
        print(f"Ingesting {pdf_path} for state {state_folder} with species {species}")
        am.ingest_file(pdf_path, state=state_folder, species=species)

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

def extract_species_from_filename(filename, valid_species):
    """
    Extract all valid species from the filename.
    Handles multi-word species (like 'black-bear') and ignores case.
    """
    filename_lower = filename.lower()
    matches = []
    for species in valid_species:
        # match on dash or underscore boundaries or anywhere in the filename
        pattern = re.escape(species.lower())
        if re.search(pattern, filename_lower):
            matches.append(species)
    return matches



if __name__ == "__main__":
    run_ingest()
