"""Unit tests for quiz.py's mock-test building and grading logic.

Uses an in-memory SQLite DB (via Flask-SQLAlchemy's app context) rather
than mocks, since these functions are mostly DB queries -- there's no
network involved, so this stays just as offline as test_scraper.py.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quiz
from app import create_app
from config import MOCK_TEST_LENGTH
from models import ContentItem, Subject, Topic, User, db


class QuizTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(test_config={"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.subject = Subject(name="Physics", slug="physics")
        db.session.add(self.subject)
        db.session.flush()
        self.topic = Topic(subject_id=self.subject.id, class_level=11, name="Motion", slug="motion")
        db.session.add(self.topic)
        db.session.flush()

        self.user = User(email="u@example.com", password_hash="x")
        self.premium_user = User(email="p@example.com", password_hash="x", is_premium=True)
        db.session.add_all([self.user, self.premium_user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def add_question(self, title, options, answer, *, is_premium=False):
        item = ContentItem(
            topic_id=self.topic.id, type="practice_question", title=title, body=title,
            options=json.dumps(options), answer=answer, is_premium=is_premium,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # ---------------------------------------------------------- correct_option

    def test_correct_option_matches_prefix(self):
        item = self.add_question(
            "2+2=?", ["3", "4", "5"], "4 (basic arithmetic)"
        )
        self.assertEqual(quiz.correct_option(item), "4")

    def test_correct_option_none_for_free_response(self):
        item = ContentItem(topic_id=self.topic.id, type="practice_question", title="Explain X", body="Explain X")
        db.session.add(item)
        db.session.commit()
        self.assertIsNone(quiz.correct_option(item))

    def test_correct_option_none_when_answer_matches_nothing(self):
        item = self.add_question("Pick one", ["A", "B"], "C (not an option)")
        self.assertIsNone(quiz.correct_option(item))

    def test_correct_option_prefers_longest_match(self):
        # "5 m/s" is a prefix of "5 m/s²" -- the answer should resolve to the
        # longer, more specific option rather than stopping at the shorter one.
        item = self.add_question("Speed?", ["5 m/s", "5 m/s²", "10 m/s"], "5 m/s² (correct)")
        self.assertEqual(quiz.correct_option(item), "5 m/s²")

    # ------------------------------------------------------ gradable_question_pool

    def test_pool_excludes_premium_for_free_user(self):
        self.add_question("Free Q", ["A", "B"], "A")
        self.add_question("Premium Q", ["A", "B"], "A", is_premium=True)

        free_pool = quiz.gradable_question_pool(
            subject_id=self.subject.id, class_level=11, topic_id=None, include_premium=False
        )
        premium_pool = quiz.gradable_question_pool(
            subject_id=self.subject.id, class_level=11, topic_id=None, include_premium=True
        )
        self.assertEqual(len(free_pool), 1)
        self.assertEqual(len(premium_pool), 2)

    def test_pool_excludes_ungradable_items(self):
        self.add_question("Gradable", ["A", "B"], "A")
        db.session.add(ContentItem(topic_id=self.topic.id, type="practice_question", title="Free response", body="x"))
        db.session.add(ContentItem(topic_id=self.topic.id, type="concept", title="A concept", body="x"))
        db.session.commit()

        pool = quiz.gradable_question_pool(
            subject_id=self.subject.id, class_level=11, topic_id=None, include_premium=True
        )
        self.assertEqual(len(pool), 1)

    # ----------------------------------------------------------- start/grade

    def test_start_attempt_caps_at_mock_test_length(self):
        for i in range(MOCK_TEST_LENGTH + 5):
            self.add_question(f"Q{i}", ["A", "B"], "A")

        attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=None
        )
        self.assertEqual(attempt.total_count, MOCK_TEST_LENGTH)

    def test_start_attempt_returns_none_when_pool_empty(self):
        attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=None
        )
        self.assertIsNone(attempt)

    def test_grade_attempt_scores_correctly(self):
        q1 = self.add_question("Q1", ["A", "B"], "A")
        q2 = self.add_question("Q2", ["A", "B"], "B")
        attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=None
        )
        self.assertEqual(attempt.total_count, 2)

        graded = quiz.grade_attempt(attempt, {str(q1.id): "A", str(q2.id): "A"})  # one right, one wrong
        self.assertEqual(graded.correct_count, 1)
        self.assertEqual(graded.score, 50.0)
        self.assertIsNotNone(graded.finished_at)

    def test_grade_attempt_missing_answer_counts_wrong(self):
        q1 = self.add_question("Q1", ["A", "B"], "A")
        attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=None
        )
        graded = quiz.grade_attempt(attempt, {})  # no answer submitted
        self.assertEqual(graded.correct_count, 0)
        self.assertEqual(graded.score, 0.0)

    # -------------------------------------------------------------- topic_accuracy

    def test_topic_accuracy_only_counts_topic_scoped_finished_attempts(self):
        q1 = self.add_question("Q1", ["A", "B"], "A")
        whole_subject_attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=None
        )
        quiz.grade_attempt(whole_subject_attempt, {str(q1.id): "A"})

        topic_attempt = quiz.start_attempt(
            user=self.user, subject_id=self.subject.id, class_level=11, topic_id=self.topic.id
        )
        quiz.grade_attempt(topic_attempt, {str(q1.id): "B"})  # wrong -> 0%

        db.session.refresh(self.user)
        rows = quiz.topic_accuracy(self.user)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["topic"].id, self.topic.id)
        self.assertEqual(rows[0]["average_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
