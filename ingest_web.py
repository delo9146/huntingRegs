# ingest_web.py

from configManager import ConfigManager
from sourceManager import SourceManager
import logging

def main():
    logging.basicConfig(level=logging.INFO)  # or DEBUG for more detail

    cfg = ConfigManager()
    sm  = SourceManager(cfg)

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
