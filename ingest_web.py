from ingestManager import IngestManager
from configManager import ConfigManager
from sourceManager import SourceManager
import logging

def main():
    logging.basicConfig(level=logging.INFO)  

    cfg = ConfigManager()
    im  = IngestManager(cfg)
    vs  = im.get_or_create_vector_store(name=cfg._config["vector_store"]["vector_store_web"])
    print(f"Web regs will land in: {vs.id}")
    sm  = SourceManager(cfg, ingest_manager=im)

    for state in cfg.sources_by_state.keys():
        logging.info("Starting ingestion for %s", state)
        try:
            sm.fetch_state_pdfs(state)
        except Exception as e:
            logging.exception("Failed to ingest %s", state)
        else:
            logging.info("Completed ingestion for %s", state)

if __name__ == "__main__":
    main()
