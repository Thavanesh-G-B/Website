"""Scrapes concept explanations from Wikipedia's public API.

Wikipedia text is licensed CC BY-SA 4.0 -- free to reuse and store as long as
attribution (source_url + "Wikipedia contributors") and the license are kept,
which we do on every ContentItem. This uses the official MediaWiki Action API
(JSON), not HTML scraping, so it's stable and doesn't need CSS selectors.

API docs: https://www.mediawiki.org/wiki/API:Main_page
"""

from __future__ import annotations

from scraper.base_scraper import ScrapeError, ScrapedItem, fetch_json

API_URL = "https://en.wikipedia.org/w/api.php"
MAX_BODY_CHARS = 4000  # keep concept entries readable, not a full textbook dump


def fetch_article_plaintext(title: str) -> tuple[str, str]:
    """Returns (canonical_title, plaintext_extract) for a Wikipedia article."""
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "format": "json",
        "titles": title,
    }
    data = fetch_json(API_URL, params=params)
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        raise ScrapeError(f"no Wikipedia page found for {title!r}")

    page = next(iter(pages.values()))
    if "missing" in page:
        raise ScrapeError(f"Wikipedia page {title!r} does not exist")

    extract = page.get("extract", "").strip()
    canonical_title = page.get("title", title)
    if not extract:
        raise ScrapeError(f"Wikipedia page {title!r} had no extractable text")
    return canonical_title, extract


def scrape_concept(job: dict) -> list[ScrapedItem]:
    """job needs: wikipedia_title (str), topic (str, used only for logging)."""
    title = job["wikipedia_title"]
    canonical_title, extract = fetch_article_plaintext(title)

    body = extract[:MAX_BODY_CHARS]
    if len(extract) > MAX_BODY_CHARS:
        body = body.rsplit("\n", 1)[0] + "\n\n[...truncated; see source for full article]"

    source_url = "https://en.wikipedia.org/wiki/" + canonical_title.replace(" ", "_")

    return [
        ScrapedItem(
            type="concept",
            title=canonical_title,
            body=body,
            source_name="Wikipedia",
            source_url=source_url,
            license="CC BY-SA 4.0",
        )
    ]
