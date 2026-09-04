# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Study Library: a local Flask + SQLite website for browsing Class 11/12 study
material (concepts and practice questions) across Math, Physics, Chemistry,
Biology and English, populated by a scraper pipeline under `scraper/`.

## Commands

```bash
pip install -r requirements.txt

python seed.py                          # add ~20 original sample items (no network needed)
python app.py                            # run the site at http://127.0.0.1:5000

python -m scraper.run_scraper            # scrape everything in scraper/sources.json
python -m scraper.run_scraper --dry-run  # list matching jobs without fetching or writing
python -m scraper.run_scraper --subject Physics --class-level 11
python -m scraper.run_scraper --type concept   # or practice_question
python -m scraper.run_scraper --topic "Laws of Motion"
python -m scraper.run_scraper --no-cache        # bypass scraper/cache/ on-disk response cache

python -m scraper.build_sources          # regenerate scraper/sources.json from TOPICS in build_sources.py

python -m unittest discover -s tests -v  # run all tests
python -m unittest tests.test_scraper.WikipediaScraperTests.test_scrape_concept_parses_extract  # single test
```

There is no build step or linter configured. Tests run fully offline against
fixtures in `scraper/fixtures/` — no network access needed to run them.

## Architecture

**Data model** (`models.py`): `Subject` → `Topic` (subject + `class_level` of
11 or 12) → `ContentItem` (`type` is `"concept"` or `"practice_question"`).
Every `ContentItem` carries `source_name`, `source_url`, and `license` for
provenance, shown on every page. The DB is a single SQLite file at
`data/app.db` (gitignored, created by `db.create_all()`).

**Web app** (`app.py`): a `create_app()` Flask factory with four routes —
`/` (subject/class grid with counts), `/subject/<slug>/<class_level>`,
`/topic/<topic_id>` (filterable by `?type=`), and `/search` (substring
match over title/body via SQLAlchemy `ilike`). Content bodies are rendered
without `|safe` deliberately, since they can contain third-party scraped
text — do not add `|safe` to user/scraped content without a good reason.

**Scraper pipeline** (`scraper/`), the part most likely to need extending:
- `base_scraper.py` — shared `fetch()`/`fetch_json()` used by every scraper
  function. Enforces robots.txt (`check_robots_allowed`, fails **closed**:
  if robots.txt itself can't be fetched, e.g. a 401/403, everything is
  treated as disallowed), per-host rate limiting (`DEFAULT_DELAY_SECONDS`),
  and on-disk response caching under `scraper/cache/` (gitignored, keyed by
  URL hash). `--no-cache` on the CLI disables cache reads for that run.
- `wikipedia_scraper.py` — the `"wikipedia"` source. Calls the MediaWiki
  Action API (JSON, not HTML) for a plain-text extract, used for
  `type: "concept"` jobs. Stable by design: no CSS selectors to maintain.
- `generic_scraper.py` — the `"generic_html"` source: a CSS-selector-driven
  scraper configured entirely from a `sources.json` job's `selectors` block
  (`item`, `title`, `body`, `options`, `answer`). This is the extension
  point for adding practice-question sources — prefer adding a
  `sources.json` entry here over writing new Python for a new site, unless
  the site needs real logic beyond selectors (in which case add a
  `scrape_xxx(job)` function and register it in `registry.py`).
- `registry.py` — maps a job's `"source"` field to its scraper function.
- `sources.json` — the actual list of scrape jobs `run_scraper.py` reads.
  Regenerated from `TOPICS` in `build_sources.py` for the ~100 curated
  Wikipedia-backed concept jobs (hand-editing `sources.json` directly for
  concept jobs will be overwritten next regen — edit `TOPICS` instead). The
  one `generic_html` job in `sources.json` is a disabled template
  (`"_disabled": true`); real practice-question jobs should be added by
  hand alongside it and are *not* touched by `build_sources.py`.
- `run_scraper.py` — CLI entry point. Filters jobs, calls the registered
  scraper function, then upserts into the DB via `get_or_create_subject` /
  `get_or_create_topic` / `upsert_item`. Dedup key for `upsert_item` is
  `(topic_id, type, title)`, so re-running is always safe.

**Seeding** (`seed.py`): ~20 hand-written sample items, not scraped — kept
separate from the scraper pipeline so the site has content even before
`run_scraper.py` is ever run.

## Scraper conventions

- New scrape sources must go through `base_scraper.fetch()`/`fetch_json()`
  (not raw `requests` calls) to get robots.txt enforcement, rate limiting,
  and caching for free.
- A `scrape_xxx(job)` function always returns `list[ScrapedItem]` (see the
  dataclass in `base_scraper.py`), never writes to the DB directly — DB
  writes are `run_scraper.py`'s job.
- Only scrape sites you have the right to scrape and store content from;
  prefer open sources (open textbooks, Wikipedia/Wikibooks, explicitly
  reusable question banks) over commercial coaching sites.
