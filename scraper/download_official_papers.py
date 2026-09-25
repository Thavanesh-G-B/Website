"""Downloads official JEE Main / NEET question papers (PDFs) from NTA's own
government archive pages, for later text extraction into ContentItems.

WHY THIS EXISTS: two third-party "PYQ database" GitHub repos were evaluated
for this project and both turned out to be unusable -- one reverse-engineered
a paywalled subscription API, the other's "verified" questions were mostly
fabricated placeholder text (see project history / commit messages around
this file). Going straight to NTA's own archive is the only source left that
can actually be trusted -- but requires downloading the real PDFs here.

IMPORTANT: this script needs a machine with normal internet access to NTA's
government domains (jeemain.nta.nic.in, neet.nta.nic.in). It will NOT work
from network-restricted sandboxes/CI -- if `fetch()` raises a connection
error, that's most likely why. Run it on your own computer.

What this script does NOT do: extract questions from the PDFs. It only
downloads the raw PDF files into scraper/official_pdfs/<exam>/. Turning
those into structured ContentItem rows (question text, options, answer,
chapter) is a separate step -- see scraper/README or ask for it once you
have some PDFs downloaded, since building a reliable parser is much easier
against real sample files than guessing blind.

Usage:
    python -m scraper.download_official_papers --exam jee_main --dry-run
    python -m scraper.download_official_papers --exam jee_main --max-pages 5
    python -m scraper.download_official_papers --exam neet --max-pages 5

The NEET archive URL below is a best guess (same NTA site family/template as
the verified JEE Main one) -- I could not verify it live from this sandbox.
If it 404s or looks wrong, find the real archive page in your browser at
https://neet.nta.nic.in/ and pass it explicitly:
    python -m scraper.download_official_papers --exam neet --base-url "https://neet.nta.nic.in/actual-archive-path/"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

from scraper.base_scraper import RobotsDisallowed, ScrapeError, fetch, fetch_binary

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "official_pdfs")

# Archive listing pages, paginated as .../page/2/, .../page/3/, etc.
# (This pagination style was confirmed for JEE Main; NEET's URL is an
# educated guess at the same site template -- verify it in your browser.)
ARCHIVE_URLS = {
    "jee_main": "https://jeemain.nta.nic.in/document-category/archive/",
    "neet": "https://neet.nta.nic.in/document-category/archive/",
}

# Only download PDFs whose link text or filename suggests an actual question
# paper (not notices, cutoffs, syllabus documents, etc.). Answer keys are
# included too since we'll need them to grade the questions later.
RELEVANT_KEYWORDS = ["question paper", "answer key", "final key", "response sheet"]


def _looks_relevant(link_text: str, href: str) -> bool:
    haystack = f"{link_text} {href}".lower()
    return any(kw in haystack for kw in RELEVANT_KEYWORDS)


def _safe_filename(url: str, link_text: str) -> str:
    """Builds a readable, collision-resistant local filename from the link
    text (human-readable) plus the original URL's filename (for uniqueness)."""
    parsed = urlparse(url)
    original_name = os.path.basename(parsed.path) or "document.pdf"
    if not original_name.lower().endswith(".pdf"):
        original_name += ".pdf"

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", link_text.strip()).strip("_")[:80]
    if slug:
        return f"{slug}__{original_name}"
    return original_name


def find_pdf_links(page_url: str) -> list[tuple[str, str]]:
    """Returns [(absolute_pdf_url, link_text), ...] found on one archive page."""
    html = fetch(page_url)
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" not in href.lower():
            continue
        text = a.get_text(strip=True) or ""
        if not _looks_relevant(text, href):
            continue
        absolute = urljoin(page_url, href)
        links.append((absolute, text))
    return links


def paginated_archive_urls(base_url: str, max_pages: int):
    yield base_url
    for page in range(2, max_pages + 1):
        yield urljoin(base_url, f"page/{page}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exam", choices=sorted(ARCHIVE_URLS), required=True)
    parser.add_argument("--base-url", help="Override the archive listing URL (use if the default 404s)")
    parser.add_argument("--max-pages", type=int, default=10, help="How many paginated archive pages to walk (default 10)")
    parser.add_argument("--limit", type=int, default=None, help="Stop after downloading this many PDFs (for a quick first test)")
    parser.add_argument("--out-dir", default=None, help="Where to save PDFs (default scraper/official_pdfs/<exam>/)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be downloaded without saving anything")
    args = parser.parse_args()

    base_url = args.base_url or ARCHIVE_URLS[args.exam]
    out_dir = args.out_dir or os.path.join(OUT_DIR, args.exam)

    print(f"Archive: {base_url}")
    print(f"Output:  {out_dir}")
    print(f"{'(dry run -- nothing will be saved)' if args.dry_run else ''}\n")

    found_total = 0
    downloaded = 0
    seen_urls = set()

    for page_url in paginated_archive_urls(base_url, args.max_pages):
        try:
            links = find_pdf_links(page_url)
        except RobotsDisallowed as exc:
            print(f"[STOP] robots.txt disallows {page_url}: {exc}")
            break
        except ScrapeError as exc:
            # Likely end of pagination (404) or -- if this is the very first
            # page -- a real connectivity problem (see module docstring).
            print(f"[stop paginating] {page_url}: {exc}")
            break

        new_links = [(u, t) for u, t in links if u not in seen_urls]
        if not new_links and page_url != base_url:
            print(f"[no new links on {page_url}, assuming end of archive]")
            break

        for pdf_url, link_text in new_links:
            seen_urls.add(pdf_url)
            found_total += 1

            if args.limit and downloaded >= args.limit:
                print(f"\nReached --limit {args.limit}, stopping.")
                _print_summary(found_total, downloaded, out_dir)
                return

            filename = _safe_filename(pdf_url, link_text)
            dest_path = os.path.join(out_dir, filename)

            if args.dry_run:
                print(f"[would download] {link_text!r} -> {filename}")
                continue

            try:
                was_downloaded = fetch_binary(pdf_url, dest_path)
                if was_downloaded:
                    downloaded += 1
                    print(f"[OK] {filename}")
                else:
                    print(f"[skip, exists] {filename}")
            except RobotsDisallowed as exc:
                print(f"[SKIP: robots.txt] {pdf_url}: {exc}")
            except ScrapeError as exc:
                print(f"[FAIL] {pdf_url}: {exc}")

    _print_summary(found_total, downloaded, out_dir)


def _print_summary(found_total: int, downloaded: int, out_dir: str):
    print(f"\nDone. {found_total} relevant PDF link(s) found, {downloaded} downloaded to {out_dir}")
    if found_total == 0:
        print(
            "\nFound nothing -- the archive page's HTML structure may not match what this "
            "script expects (govt sites change layouts), or --base-url needs correcting. "
            "Open the archive URL in your own browser to check, then share what you see."
        )


if __name__ == "__main__":
    main()
