"""Shared scraping infrastructure: polite HTTP fetching, robots.txt checks,
rate limiting, and on-disk caching so re-runs don't hammer the same site.

Design goals:
  - Never fetch a URL that the site's robots.txt disallows for our user agent.
  - Always wait between requests to the same host (be a good citizen).
  - Cache raw responses to disk so re-running the scraper (e.g. after fixing
    a parser bug) doesn't re-download everything.
  - Fail loudly but don't crash the whole run on one bad URL.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "StudyLibraryBot/1.0 (+local educational content aggregator; "
    "contact: set-your-contact-email-in-base_scraper.py)"
)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
DEFAULT_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT = 20

os.makedirs(CACHE_DIR, exist_ok=True)

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
_last_request_time: dict[str, float] = {}


class ScrapeError(Exception):
    pass


class RobotsDisallowed(ScrapeError):
    """Raised when robots.txt forbids fetching a URL."""


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _cache_path(url: str) -> str:
    return os.path.join(CACHE_DIR, _cache_key(url) + ".cache")


def _get_robot_parser(url: str) -> urllib.robotparser.RobotFileParser:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(origin + "/robots.txt")
        try:
            rp.read()
        except Exception:
            # If robots.txt can't be fetched/parsed, default to allow (most
            # sites don't have one) but this is logged so it's not silent.
            print(f"[base_scraper] warning: could not read robots.txt for {origin}")
        _robots_cache[origin] = rp
    return _robots_cache[origin]


def check_robots_allowed(url: str) -> bool:
    rp = _get_robot_parser(url)
    return rp.can_fetch(USER_AGENT, url)


def _throttle(url: str, delay: float) -> None:
    host = urlparse(url).netloc
    last = _last_request_time.get(host)
    now = time.time()
    if last is not None:
        elapsed = now - last
        if elapsed < delay:
            time.sleep(delay - elapsed)
    _last_request_time[host] = time.time()


def fetch(
    url: str,
    *,
    delay: float = DEFAULT_DELAY_SECONDS,
    use_cache: bool = True,
    respect_robots: bool = True,
    params: dict | None = None,
    headers: dict | None = None,
) -> str:
    """Fetch a URL as text, honoring robots.txt, rate limiting, and cache.

    Raises RobotsDisallowed if robots.txt forbids fetching, or ScrapeError on
    any other failure (network error, bad status code).
    """
    full_url = url
    if params:
        # Build a cache-stable key that includes params.
        full_url = requests.Request("GET", url, params=params).prepare().url

    if respect_robots and not check_robots_allowed(full_url):
        raise RobotsDisallowed(f"robots.txt disallows fetching {full_url}")

    cache_file = _cache_path(full_url)
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    _throttle(full_url, delay)

    req_headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    if headers:
        req_headers.update(headers)

    try:
        resp = requests.get(full_url, headers=req_headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapeError(f"failed to fetch {full_url}: {exc}") from exc

    text = resp.text
    if use_cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def fetch_json(url: str, **kwargs) -> dict:
    text = fetch(url, **kwargs)
    return json.loads(text)


@dataclass
class ScrapedItem:
    """One scraped content item, ready to be written to the ContentItem table."""

    type: str  # "concept" | "practice_question"
    title: str
    body: str
    options: list[str] | None = None
    answer: str | None = None
    difficulty: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    license: str | None = None
