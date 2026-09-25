"""Offline tests for scraper/extract_pyq_images.py: PDF parsing (via saved
fixtures) and the import_questions() DB-writing path (via an in-memory DB,
same pattern as test_quiz.py).

Uses small synthetic fixture PDFs (scraper/fixtures/pyq_*_sample.pdf) that
mimic the real NTA export format's structure -- made-up arithmetic
questions ("What is 2 + 2?"), not real exam content.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.extract_pyq_images import import_questions, parse_answer_key, parse_question_paper

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper", "fixtures")
QUESTION_PAPER = os.path.join(FIXTURES, "pyq_question_paper_sample.pdf")
ANSWER_KEY = os.path.join(FIXTURES, "pyq_answer_key_sample.pdf")


class ParseQuestionPaperTests(unittest.TestCase):
    def setUp(self):
        self.questions = parse_question_paper(QUESTION_PAPER)

    def test_extracts_both_questions(self):
        self.assertEqual(len(self.questions), 2)

    def test_mcq_question_has_four_options_with_images(self):
        mcq = next(q for q in self.questions if q.question_type == "MCQ")
        self.assertEqual(mcq.question_id, "6910011001")
        self.assertEqual(mcq.subject, "Mathematics")
        self.assertEqual(len(mcq.options), 4)
        self.assertEqual(
            [o.option_id for o in mcq.options],
            ["6910012001", "6910012002", "6910012003", "6910012004"],
        )
        for opt in mcq.options:
            self.assertGreater(len(opt.image_bytes), 0)
        self.assertGreater(len(mcq.stem_image_bytes), 0)
        self.assertIsNone(mcq.numeric_answer)

    def test_numerical_question_has_embedded_answer_no_options(self):
        sa = next(q for q in self.questions if q.question_type == "SA")
        self.assertEqual(sa.question_id, "6910011002")
        self.assertEqual(sa.options, [])
        self.assertEqual(sa.numeric_answer, "42")
        self.assertGreater(len(sa.stem_image_bytes), 0)


class ParseAnswerKeyTests(unittest.TestCase):
    def test_maps_question_id_to_correct_option_id(self):
        answers = parse_answer_key(ANSWER_KEY)
        self.assertEqual(answers.get("6910011001"), "6910012003")

    def test_drop_entries_are_excluded(self):
        answers = parse_answer_key(ANSWER_KEY)
        self.assertNotIn("9999999", answers)


class EndToEndMatchTests(unittest.TestCase):
    """Confirms a Question Paper + its matching Answer Key resolve to a
    real correct answer -- the actual thing this pipeline exists for."""

    def test_mcq_correct_option_resolves_via_answer_key(self):
        questions = parse_question_paper(QUESTION_PAPER)
        answers = parse_answer_key(ANSWER_KEY)
        mcq = next(q for q in questions if q.question_type == "MCQ")

        correct_id = answers.get(mcq.question_id)
        option_ids = [o.option_id for o in mcq.options]

        self.assertIn(correct_id, option_ids)
        self.assertEqual(correct_id, "6910012003")


class ImportQuestionsTests(unittest.TestCase):
    """Exercises import_questions()'s DB-writing path end-to-end against an
    in-memory DB (same pattern as test_quiz.py's setUp)."""

    TOPIC_NAME = "Test Fixture Session (delete-me)"

    def setUp(self):
        from app import create_app
        from models import db

        self.app = create_app(test_config={"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.db = db

        self.images_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "pyq_images",
        )

    def tearDown(self):
        # Clean up any image files written under this test's topic slug --
        # import_questions() saves real files to static/, which isn't part
        # of the in-memory DB it otherwise runs against.
        from slugify_util import slugify

        slug_dir = os.path.join(self.images_dir, slugify(self.TOPIC_NAME))
        if os.path.isdir(slug_dir):
            shutil.rmtree(slug_dir)

        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def test_import_creates_gradable_mcq_and_ungraded_numerical_item(self):
        from models import ContentItem, Subject, Topic

        inserted, skipped_existing, skipped_unmapped = import_questions(
            question_paper_path=QUESTION_PAPER,
            answer_key_path=ANSWER_KEY,
            subject_map={"Mathematics": "Math"},
            class_level=12,
            topic_name=self.TOPIC_NAME,
            is_premium=False,
        )

        self.assertEqual(inserted, 2)
        self.assertEqual(skipped_existing, 0)
        self.assertEqual(skipped_unmapped, 0)

        subject = Subject.query.filter_by(name="Math").first()
        self.assertIsNotNone(subject)
        topic = Topic.query.filter_by(subject_id=subject.id, class_level=12).first()
        self.assertEqual(topic.name, self.TOPIC_NAME)

        items = ContentItem.query.filter_by(topic_id=topic.id).order_by(ContentItem.id).all()
        self.assertEqual(len(items), 2)

        mcq_item = next(i for i in items if i.option_images)
        self.assertFalse(mcq_item.is_premium)
        self.assertTrue(os.path.exists(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", mcq_item.body_image
        )))
        # The answer key matched this question -- the correct option ID
        # should have made it onto the row, and be gradable end-to-end.
        from quiz import correct_option
        self.assertEqual(mcq_item.answer, "6910012003")
        self.assertIn(mcq_item.answer, json.loads(mcq_item.options))
        self.assertEqual(correct_option(mcq_item), "6910012003")

        sa_item = next(i for i in items if not i.option_images)
        self.assertEqual(sa_item.answer, "42")
        self.assertIsNone(sa_item.options)

    def test_rerunning_import_skips_existing_items(self):
        import_questions(
            question_paper_path=QUESTION_PAPER, answer_key_path=ANSWER_KEY,
            subject_map={"Mathematics": "Math"}, class_level=12, topic_name=self.TOPIC_NAME,
        )
        inserted, skipped_existing, _ = import_questions(
            question_paper_path=QUESTION_PAPER, answer_key_path=ANSWER_KEY,
            subject_map={"Mathematics": "Math"}, class_level=12, topic_name=self.TOPIC_NAME,
        )
        self.assertEqual(inserted, 0)
        self.assertEqual(skipped_existing, 2)

    def test_unmapped_subject_is_skipped(self):
        inserted, _, skipped_unmapped = import_questions(
            question_paper_path=QUESTION_PAPER, answer_key_path=ANSWER_KEY,
            subject_map={"SomeOtherSubject": "Whatever"},  # doesn't match "Mathematics"
            class_level=12, topic_name=self.TOPIC_NAME,
        )
        self.assertEqual(inserted, 0)
        self.assertEqual(skipped_unmapped, 2)


if __name__ == "__main__":
    unittest.main()
