# sourceManager.py
import os
import time
import requests
from bs4 import BeautifulSoup
from configManager import ConfigManager
from fileManager import FileManager

class SourceManager:
    def __init__(self, cfg: ConfigManager):
        self.cfg = cfg
        self.fm = FileManager(cfg.input_dir, cfg.output_dir)

    def fetch_state_pdfs(self, state: str):
        """
        For each URL in cfg.sources_by_state[state]:
          1. GET the page.
          2. Parse <a href="*.pdf"> links.
          3. Download new or updated PDFs into data/input/<state>/.
        """
        urls = self.cfg.sources_by_state.get(state, [])
        state_dir = os.path.join(self.fm.input_dir, state)
        os.makedirs(state_dir, exist_ok=True)

        for page_url in urls:
            resp = requests.get(page_url); resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.select("a[href$='.pdf']"):
                pdf_url = a["href"]
                # resolve relative links
                if not pdf_url.startswith("http"):
                    pdf_url = requests.compat.urljoin(page_url, pdf_url)

                orig = os.path.basename(pdf_url)
                new_name = self._normalize_filename(orig)
                local_path = os.path.join(state_dir, new_name)

                # check Last-Modified header vs. local file mtime
                head = requests.head(pdf_url, allow_redirects=True)
                remote_mod = head.headers.get("Last-Modified")
                local_mod = time.ctime(os.path.getmtime(local_path)) if os.path.exists(local_path) else None

                if (not os.path.exists(local_path)) or (remote_mod and remote_mod != local_mod):
                    print(f"↓ Fetching {state}/{new_name}")
                    data = requests.get(pdf_url).content
                    with open(local_path, "wb") as f:
                        f.write(data)
                    if remote_mod:
                        # update local mtime to match remote
                        ts = time.mktime(time.strptime(remote_mod, "%a, %d %b %Y %H:%M:%S %Z"))
                        os.utime(local_path, (ts, ts))

    _NAME_MAP = {
        "dea":      "deer-elk-antelope",
        "msgb": "moose-sheep-goat-bison",
        "mig-bird":         "migratory-bird",
        "upgbrd":       "upland-game-bird",
        "wolf-and-furbearer":     "wolf-furbearer",
    }                  

    def _normalize_filename(self, orig_fname: str) -> str:
        """
        Turn e.g. '2025-deer-elk-antelope-regulations-final.pdf'
        into 'dea.pdf', etc.
        """
        slug, ext = os.path.splitext(orig_fname.lower())
        for long_name, code in self._NAME_MAP.items():
            if long_name in slug:
                return f"{code}{ext}"
        # no match → leave original
        return orig_fname
