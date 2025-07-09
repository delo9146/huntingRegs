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
        if state.lower() == "colorado":
            return self._fetch_colorado_rules()
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
                self._download_pdf(state, pdf_url)

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

    def _fetch_colorado_rules(self):
        """
        Download every Chapter W-XX PDF under 'Wildlife Regulations',
        in numeric order, skipping all non-W chapters.
        """
        base_url = self.cfg.sources_by_state["colorado"][0]
        print(f"🔍 Scanning Colorado regulations hub: {base_url}")
        resp = self.session.get(base_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Find all 'Download' links anywhere on the page
        download_links = soup.find_all("a", string=re.compile(r"download", re.I))
        candidates = set()
        for a in download_links:
            href = a.get("href")
            if href:
                candidates.add(urljoin(base_url, href))

        # 2) Filter for only W-chapter PDF URLs
        #    Match filenames like 'chapter-w-02-…' or 'ch02.pdf'
        pat = re.compile(r'^(?:chapter-w-(\d{1,2})|ch(\d{1,2}))', re.IGNORECASE)
        numbered = []
        for url in candidates:
            fname = os.path.basename(url).split("?")[0].lower()
            m = pat.match(fname)
            if not m:
                continue
            chap_num = int(m.group(1) or m.group(2))
            numbered.append((chap_num, url))

        # 3) Sort by chapter number
        numbered.sort(key=lambda x: x[0])

        # 4) Download in order
        if not numbered:
            print("  • No W-chapter PDFs found!")
        for num, pdf_url in numbered:
            self._download_pdf("colorado", pdf_url)




    def _download_pdf(self, state: str, pdf_url: str):
        """
        Normalize, check Last-Modified, and download a PDF into data/input/<state>.
        """
        # ➊ normalize the filename
        orig      = os.path.basename(pdf_url.split("?")[0])
        new_name  = self._normalize_filename(orig)

        # ➋ ensure the state directory exists
        dest_dir  = os.path.join(self.fm.input_dir, state)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, new_name)

        # ➌ HEAD for Last-Modified
        try:
            head       = self.session.head(pdf_url, allow_redirects=True, timeout=5)
            remote_mod = head.headers.get("Last-Modified")
        except requests.RequestException:
            remote_mod = None

        # If we hit an HTML “viewer” page instead of a PDF, chase the real PDF URL
        ctype = head.headers.get("Content-Type", "")
        if "text/html" in ctype.lower():
            # fetch the viewer page
            resp = self.session.get(pdf_url, timeout=5)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1) try an <iframe> whose src ends in .pdf
            iframe = soup.find("iframe", src=re.compile(r"\.pdf$", re.I))
            if iframe:
                pdf_url = urljoin(pdf_url, iframe["src"])
            else:
                # 2) fallback: look for the JS variable window.viewerPdfUrl
                m = re.search(r"window\.viewerPdfUrl\s*=\s*'([^']+)'", resp.text)
                if m:
                    pdf_url = m.group(1)

            # now re-HEAD the real PDF for timestamp checking
            head       = self.session.head(pdf_url, allow_redirects=True, timeout=5)
            remote_mod = head.headers.get("Last-Modified")

        # ➍ skip if unchanged
        if os.path.exists(dest_path) and remote_mod:
            local_mod = time.ctime(os.path.getmtime(dest_path))
            if local_mod == remote_mod:
                return

        # ➎ fetch & write
        print(f"↓ Fetching {state}/{new_name}")
        try:
            data = self.session.get(pdf_url, timeout=10).content
            with open(dest_path, "wb") as f:
                f.write(data)
            # ➏ set mtime to remote_mod for future diffs
            if remote_mod:
                ts = time.mktime(time.strptime(remote_mod, "%a, %d %b %Y %H:%M:%S %Z"))
                os.utime(dest_path, (ts, ts))
        except requests.RequestException as e:
            print(f"  ! Download failed for {pdf_url}: {e}")