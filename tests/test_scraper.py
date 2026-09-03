"""Unit tests for the scraper's parsing logic.

These deliberately never touch the real network -- they patch base_scraper's
fetch/fetch_json functions with saved fixtures, so they run the same
offline as online (useful in sandboxes/CI where outbound access to
arbitrary sites may be restricted).
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import wikipedia_scraper
from scraper.base_scraper import RobotsDisallowed, ScrapeError
from scraper.generic_scraper import scrape_generic_html

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


class WikipediaScraperTests(unittest.TestCase):
    def test_scrape_concept_parses_extract(self):
        fixture = json.loads(load_fixture("wikipedia_kinematics.json"))
        with patch("scraper.wikipedia_scraper.fetch_json", return_value=fixture) as mock_fetch:
            items = wikipedia_scraper.scrape_concept({"wikipedia_title": "Kinematics"})

        mock_fetch.assert_called_once()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.type, "concept")
        self.assertEqual(item.title, "Kinematics")
        self.assertIn("subfield of physics", item.body)
        self.assertEqual(item.source_name, "Wikipedia")
        self.assertEqual(item.source_url, "https://en.wikipedia.org/wiki/Kinematics")
        self.assertEqual(item.license, "CC BY-SA 4.0")

    def test_missing_page_raises(self):
        fixture = {"query": {"pages": {"-1": {"ns": 0, "title": "Nonexistent", "missing": ""}}}}
        with patch("scraper.wikipedia_scraper.fetch_json", return_value=fixture):
            with self.assertRaises(ScrapeError):
                wikipedia_scraper.scrape_concept({"wikipedia_title": "Nonexistent"})

    def test_long_extract_is_truncated(self):
        long_text = "Sentence. " * 2000  # way over MAX_BODY_CHARS
        fixture = {"query": {"pages": {"1": {"title": "Long Topic", "extract": long_text}}}}
        with patch("scraper.wikipedia_scraper.fetch_json", return_value=fixture):
            items = wikipedia_scraper.scrape_concept({"wikipedia_title": "Long Topic"})
        self.assertLessEqual(len(items[0].body), wikipedia_scraper.MAX_BODY_CHARS + 100)
        self.assertIn("truncated", items[0].body)


class GenericScraperTests(unittest.TestCase):
    def test_scrape_generic_html_extracts_all_questions(self):
        html = load_fixture("practice_questions.html")
        job = {
            "url": "https://example.com/practice",
            "type": "practice_question",
            "source_name": "Example Site",
            "license": "Test fixture",
            "selectors": {
                "item": "div.question",
                "title": ".question-text",
                "options": ".options li",
                "answer": ".answer",
            },
        }
        with patch("scraper.generic_scraper.fetch", return_value=html):
            items = scrape_generic_html(job)

        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "What is the SI unit of force?")
        self.assertEqual(first.options, ["Joule", "Newton", "Watt", "Pascal"])
        self.assertEqual(first.answer, "Newton")
        self.assertEqual(first.source_url, "https://example.com/practice")
        self.assertEqual(first.license, "Test fixture")

    def test_bad_selector_raises(self):
        html = load_fixture("practice_questions.html")
        job = {
            "url": "https://example.com/practice",
            "selectors": {"item": "div.nonexistent-class"},
        }
        with patch("scraper.generic_scraper.fetch", return_value=html):
            with self.assertRaises(ScrapeError):
                scrape_generic_html(job)


class RobotsTests(unittest.TestCase):
    def test_disallowed_url_raises_before_network_call(self):
        from scraper import base_scraper

        class FakeRobotParser:
            def can_fetch(self, agent, url):
                return False

        with patch.object(base_scraper, "_get_robot_parser", return_value=FakeRobotParser()):
            with self.assertRaises(RobotsDisallowed):
                base_scraper.fetch("https://example.com/disallowed-page", use_cache=False)


if __name__ == "__main__":
    unittest.main()
