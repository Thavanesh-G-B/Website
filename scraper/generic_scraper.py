"""A configurable CSS-selector-driven scraper for arbitrary HTML pages.

Use this to plug in a specific website (a textbook site, an open question
bank, your school's resource page, etc.) without writing new Python code --
just add an entry to sources.json with "source": "generic_html" and the
CSS selectors that pick out the content on that page.

You are responsible for making sure you're allowed to scrape and store
content from whatever URL you configure here (check the site's Terms of
Service / robots.txt; base_scraper already refuses to fetch anything
robots.txt disallows).

sources.json entry shape:
{
    "subject": "Physics",
    "class_level": 11,
    "topic": "Laws of Motion",
    "type": "practice_question",
    "source": "generic_html",
    "url": "https://example.com/class-11-physics/laws-of-motion",
    "source_name": "Example Site",
    "license": "Check site terms before reuse",
    "selectors": {
        "item": "div.question",        // required: one CSS selector per question/concept block
        "title": ".question-text",     // required: relative to each item
        "body": ".explanation",        // optional: extra body text, concatenated after title
        "options": ".options li",      // optional: multiple choice options, relative to item
        "answer": ".answer"            // optional: relative to item
    }
}

For a "concept" page that isn't a repeated list (e.g. one article), omit
"item" and set selectors.title / selectors.body directly against the page.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.base_scraper import ScrapeError, ScrapedItem, fetch


def _text(el) -> str | None:
    if el is None:
        return None
    return el.get_text(strip=True, separator=" ")


def _extract_one(container, selectors: dict, *, item_type: str, source_name, source_url, license_) -> ScrapedItem:
    title_sel = selectors.get("title")
    title_el = container.select_one(title_sel) if title_sel else None
    title = _text(title_el)
    if not title:
        raise ScrapeError(f"selector {title_sel!r} matched no title text")

    body_sel = selectors.get("body")
    body = _text(container.select_one(body_sel)) if body_sel else None
    if not body:
        body = title

    options = None
    options_sel = selectors.get("options")
    if options_sel:
        opts = [_text(o) for o in container.select(options_sel)]
        options = [o for o in opts if o]

    answer = None
    answer_sel = selectors.get("answer")
    if answer_sel:
        answer = _text(container.select_one(answer_sel))

    return ScrapedItem(
        type=item_type,
        title=title,
        body=body,
        options=options or None,
        answer=answer,
        source_name=source_name,
        source_url=source_url,
        license=license_,
    )


def scrape_generic_html(job: dict) -> list[ScrapedItem]:
    url = job["url"]
    selectors = job.get("selectors", {})
    item_type = job.get("type", "practice_question")
    source_name = job.get("source_name")
    license_ = job.get("license")

    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    item_sel = selectors.get("item")
    if item_sel:
        containers = soup.select(item_sel)
        if not containers:
            raise ScrapeError(f"selector {item_sel!r} matched nothing on {url}")
        results = []
        for container in containers:
            try:
                results.append(
                    _extract_one(
                        container, selectors, item_type=item_type,
                        source_name=source_name, source_url=url, license_=license_,
                    )
                )
            except ScrapeError as exc:
                print(f"[generic_scraper] skipping one item on {url}: {exc}")
        return results
    else:
        return [
            _extract_one(
                soup, selectors, item_type=item_type,
                source_name=source_name, source_url=url, license_=license_,
            )
        ]
