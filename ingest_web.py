# ingest_web.py

from configManager import ConfigManager
from sourceManager import SourceManager

def main():
    # Load config and init scraper
    cfg = ConfigManager()
    sm = SourceManager(cfg)

    state = "colorado"
    print(f"🔄 Starting web ingestion for '{state}'...")

    # Download all linked PDFs for Montana
    sm.fetch_state_pdfs(state)

    print(f"✅ Web ingestion for '{state}' completed.")

if __name__ == "__main__":
    main()
