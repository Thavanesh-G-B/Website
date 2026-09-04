# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Study Library: a local Flask + SQLite website for browsing Class 11/12 study
material (concepts and practice questions) across Math, Physics, Chemistry,
Biology and English, populated by a scraper pipeline under `scraper/`. Also
has accounts, a free/premium practice-question tier, auto-graded mock
tests, and a progress dashboard (see Monetization section below) — no ads
on either tier.

## Commands

```bash
pip install -r requirements.txt

python seed.py                          # add ~30 original sample items, some is_premium=True (no network needed)
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
python -m unittest tests.test_quiz.QuizTestCase.test_grade_attempt_scores_correctly              # single test
```

There is no build step or linter configured. Tests run fully offline:
`test_scraper.py` against fixtures in `scraper/fixtures/`, `test_quiz.py`
against an in-memory SQLite DB (`create_app(test_config={...})` — see
Architecture below for why the factory needs the `test_config` param).

## Architecture

**Data model** (`models.py`): `Subject` → `Topic` (subject + `class_level` of
11 or 12) → `ContentItem` (`type` is `"concept"` or `"practice_question"`).
Every `ContentItem` carries `source_name`, `source_url`, and `license` for
provenance, shown on every page, plus `is_premium` (only ever `True` on
`practice_question` rows — concepts are never gated, see Monetization).
`User` (Flask-Login `UserMixin`, `is_premium` flag) and `Attempt` (one mock
test: a fixed `question_ids` JSON list chosen at start time, `answers` JSON
submitted at grading time, resulting `score`) round out the schema. The DB
is a single SQLite file at `data/app.db` (gitignored, created by
`db.create_all()`).

**Web app** (`app.py`): a `create_app(test_config=None)` Flask factory.
`test_config` is applied to `app.config` *before* `db.init_app(app)` so
tests can point at `sqlite:///:memory:` instead of the real `data/app.db`
— setting it after `create_app()` returns has no effect, since the engine
is already bound by then (see `tests/test_quiz.py`). Routes: browsing (`/`,
`/subject/<slug>/<class_level>`, `/topic/<topic_id>` filterable by `?type=`,
`/search` via SQLAlchemy `ilike`), auth (`/register`, `/login`, `/logout`),
`/upgrade` + `/upgrade/activate` + `/upgrade/cancel` (premium toggle — dev
stub, see Monetization), `/practice-test*` (mock test form/take/result, all
`@login_required`), `/progress` (`@login_required`). Content bodies are
rendered without `|safe` deliberately, since they can contain third-party
scraped text — do not add `|safe` to user/scraped content without a good
reason. Locked (`is_premium=True`, viewer not premium) practice questions
render title + a lock badge only — never body/options/answer — in both
`topic_view` and `search`.

**Mock tests / grading** (`quiz.py`, separate from `app.py` so the grading
logic is unit-testable without going through routes): `correct_option(item)`
figures out which of a question's `options` is correct by checking which
one `item.answer` (a free-text field written as `"<exact option
text>(optional explanation)"`) starts with — preferring the *longest*
matching option, since one option's text can be a prefix of another's (e.g.
`"5 m/s"` vs `"5 m/s²"`). A `ContentItem` with no `options`, or whose
`answer` doesn't start with any of them, is excluded from
`gradable_question_pool()` (browsable on the topic page, just never used in
a scored test). `start_attempt()` shuffles the eligible pool (respecting
`include_premium`) and caps at `MOCK_TEST_LENGTH`; `grade_attempt()`
compares submitted answers against `correct_option()` and persists the
score. `topic_accuracy()` only considers topic-scoped attempts (whole-subject
attempts mix topics, so they're excluded from the per-topic breakdown but
still count toward the subject-level average on `/progress`).

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

**Seeding** (`seed.py`): ~30 hand-written sample items, not scraped — kept
separate from the scraper pipeline so the site has content (including a
gradable mock test in every seeded topic, both free and premium tiers)
even before `run_scraper.py` is ever run. Three lists: `SAMPLE_DATA` (one
concept + one practice question per topic), `EXTRA_FREE_QUESTIONS` (a
second free MCQ per topic, so free accounts clear `MOCK_TEST_MIN_QUESTIONS`
on their own), `PREMIUM_QUESTIONS` (`is_premium=True`). All scraped content
(via `run_scraper.py`) defaults to `is_premium=False` — the scraper doesn't
know about premium tiering; that's curated by hand in `seed.py` or set
directly on `ContentItem` rows.

## Monetization

Concepts are always free (Wikipedia-sourced, CC BY-SA — nothing to charge
for). Only a subset of practice questions are `is_premium=True`, and
premium accounts get a larger mock-test question pool. **No payment
gateway is wired in** — `/upgrade/activate` in `app.py` just flips
`User.is_premium` directly from a client POST, which is fine for local/dev
use but is explicitly documented in that route's comment as unsafe to ship
as-is: a real launch needs a Checkout Session route plus a payment
provider's webhook (not a client POST) setting `is_premium=True`.

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
