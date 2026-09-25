"""Offline tests for the official-PDF-archive link parsing logic in
scraper/download_official_papers.py.

These test find_pdf_links()'s filtering against a saved HTML fixture (not a
live NTA page -- this sandbox can't reach nta.nic.in, see that module's
docstring), plus the filename-safety helper. They can't prove the real
archive's HTML matches this fixture's structure, but they do prove the
keyword-filtering and filename logic itself is correct, and will catch
regressions if that logic changes.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.download_official_papers import _safe_filename, find_pdf_links

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


class FindPdfLinksTests(unittest.TestCase):
    def test_filters_to_relevant_documents_only(self):
        html = load_fixture("nta_archive_page.html")
        with patch("scraper.download_official_papers.fetch", return_value=html):
            links = find_pdf_links("https://jeemain.nta.nic.in/document-category/archive/")

        texts = [text for _url, text in links]
        # Question papers, answer keys, and response sheets should be kept...
        self.assertTrue(any("Question Paper" in t for t in texts))
        self.assertTrue(any("Final Answer Key" in t for t in texts))
        self.assertTrue(any("Response Sheet" in t for t in texts))
        # ...but generic notices/circulars/syllabus should be filtered out.
        self.assertFalse(any("Public Notice" in t for t in texts))
        self.assertFalse(any("Syllabus" in t for t in texts))
        self.assertFalse(any("Circular" in t for t in texts))
        self.assertEqual(len(links), 3)

    def test_relative_links_resolved_to_absolute(self):
        html = load_fixture("nta_archive_page.html")
        with patch("scraper.download_official_papers.fetch", return_value=html):
            links = find_pdf_links("https://jeemain.nta.nic.in/document-category/archive/")

        urls = [url for url, _text in links]
        self.assertTrue(any(u.startswith("https://jeemain.nta.nic.in/uploads/") for u in urls))
        # An already-absolute link (different CDN host) should be preserved as-is.
        self.assertTrue(any(u.startswith("https://cdnbbsr.s3waas.gov.in/") for u in urls))


class SafeFilenameTests(unittest.TestCase):
    def test_combines_slug_and_original_name(self):
        name = _safe_filename(
            "https://jeemain.nta.nic.in/uploads/2025/04/qp_27apr_s1.pdf",
            "JEE Main 2025 Session 2 Question Paper (27 Apr, Shift 1)",
        )
        self.assertTrue(name.endswith("qp_27apr_s1.pdf"))
        self.assertTrue(name.startswith("JEE_Main_2025"))
        self.assertNotIn(" ", name)
        self.assertNotIn("(", name)

    def test_adds_pdf_extension_if_missing_from_url(self):
        name = _safe_filename("https://example.gov.in/download?doc=12345", "Answer Key")
        self.assertTrue(name.endswith(".pdf"))

    def test_falls_back_to_original_name_if_text_empty(self):
        name = _safe_filename("https://example.gov.in/uploads/paper.pdf", "")
        self.assertEqual(name, "paper.pdf")


if __name__ == "__main__":
    unittest.main()
