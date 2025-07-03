# sourceManager.py

import os
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from configManager import ConfigManager
from fileManager import FileManager

class SourceManager:
    def __init__(self, cfg: ConfigManager):
        self.cfg     = cfg
        self.fm      = FileManager(cfg.input_dir, cfg.output_dir)
        # browser‐like session to avoid 403s
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    # Map short code → full slug
    _NAME_MAP = {
        "dea":                "deer-elk-antelope",
        "msgb":               "moose-sheep-goat-bison",
        "mig-bird":           "migratory-bird",
        "upgbrd":             "upland-game-bird",
        "wolf-and-furbearer": "wolf-furbearer",
    }

    def _normalize_filename(self, orig_fname: str) -> str:
        """
        Swap in the long slug but preserve year/suffix, and
        guarantee a .pdf extension.
        """
        base, ext = os.path.splitext(orig_fname)
        if ext.lower() != ".pdf":
            ext = ".pdf"

        for code, long_slug in self._NAME_MAP.items():
            pattern = re.compile(re.escape(code), re.IGNORECASE)
            if pattern.search(base):
                return pattern.sub(long_slug, base) + ext

        return base + ext

    def _find_pdf_links(self, page_url: str, soup: BeautifulSoup) -> set[str]:
        """
        1) From the CPW page, only look at <a> whose text contains
           'download' or 'brochure' (filters out Spanish 'Descargue').
        2) And whose href mentions .pdf, widen.net, or widencollective.com.
        3) HEAD-check for real PDFs or chase the iframe/link in viewer pages.
        """
        pdf_urls = set()
        candidates = []

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if not ("download" in text or "brochure" in text):
                continue

            href = a["href"]
            if any(tok in href.lower() for tok in [".pdf", "widen.net", "widencollective.com"]):
                candidates.append(urljoin(page_url, href))

        for link in candidates:
            try:
                head = self.session.head(link, allow_redirects=True, timeout=5)
                ctype = head.headers.get("Content-Type", "")
            except requests.RequestException:
                ctype = ""

            # direct PDF?
            if link.lower().endswith(".pdf") or "application/pdf" in ctype:
                pdf_urls.add(link)
                continue

            # chase viewer/share page
            try:
                sub = self.session.get(link, timeout=5)
                sub.raise_for_status()
                sub_soup = BeautifulSoup(sub.text, "html.parser")
            except requests.RequestException:
                continue

            # iframe → PDF
            iframe = sub_soup.find("iframe", src=True)
            if iframe and iframe["src"].lower().endswith(".pdf"):
                pdf_urls.add(urljoin(link, iframe["src"]))
                continue

            # <link type="application/pdf">
            link_tag = sub_soup.find("link", {"type": "application/pdf"})
            if link_tag:
                href2 = link_tag.get("href", "")
                if href2.lower().endswith(".pdf"):
                    pdf_urls.add(urljoin(link, href2))

        return pdf_urls

    def fetch_state_pdfs(self, state: str):
        urls      = self.cfg.sources_by_state.get(state, [])
        state_dir = os.path.join(self.fm.input_dir, state)
        os.makedirs(state_dir, exist_ok=True)

        for page_url in urls:
            print(f"🔍 Scanning {page_url}")
            try:
                resp = self.session.get(page_url, allow_redirects=True, timeout=10)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  ! Failed to fetch {page_url}: {e}")
                continue

            soup     = BeautifulSoup(resp.text, "html.parser")
            pdf_urls = self._find_pdf_links(page_url, soup)

            if not pdf_urls:
                print(f"  • No English PDFs found on {page_url}")

            for pdf_url in pdf_urls:
                orig       = os.path.basename(pdf_url.split("?")[0])
                new_name   = self._normalize_filename(orig)
                local_path = os.path.join(state_dir, new_name)

                # check Last-Modified
                try:
                    head       = self.session.head(pdf_url, allow_redirects=True, timeout=5)
                    remote_mod = head.headers.get("Last-Modified")
                except:
                    remote_mod = None

                local_mod = (
                    time.ctime(os.path.getmtime(local_path))
                    if os.path.exists(local_path)
                    else None
                )

                if not os.path.exists(local_path) or (remote_mod and remote_mod != local_mod):
                    print(f"↓ Fetching {state}/{new_name}")
                    try:
                        data = self.session.get(pdf_url, timeout=10).content
                        with open(local_path, "wb") as f:
                            f.write(data)
                        if remote_mod:
                            ts = time.mktime(time.strptime(
                                remote_mod, "%a, %d %b %Y %H:%M:%S %Z"
                            ))
                            os.utime(local_path, (ts, ts))
                    except requests.RequestException as e:
                        print(f"  ! Download failed for {pdf_url}: {e}")
