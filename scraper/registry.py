"""Maps a job's "source" field to the scraper function that handles it.

To add a brand-new site-specific scraper (e.g. because a site's structure
needs custom logic that CSS selectors alone can't express), write a
scrape_xxx(job) -> list[ScrapedItem] function in its own module and register
it here. Most new sites, though, should just use "generic_html" in
sources.json (see generic_scraper.py's docstring).
"""

from scraper.generic_scraper import scrape_generic_html
from scraper.wikipedia_scraper import scrape_concept as scrape_wikipedia_concept

SCRAPERS = {
    "wikipedia": scrape_wikipedia_concept,
    "generic_html": scrape_generic_html,
}


def get_scraper(source: str):
    try:
        return SCRAPERS[source]
    except KeyError:
        raise ValueError(
            f"Unknown source {source!r} in sources.json. Known sources: {sorted(SCRAPERS)}"
        )
