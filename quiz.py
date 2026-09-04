"""Mock-test building and grading logic, kept separate from app.py routes.

A ContentItem is only usable in an auto-graded mock test if it's multiple
choice (has `options`) AND its `answer` field identifies which option is
correct. Existing content writes `answer` as "<exact option text>(optional
explanation)" -- e.g. options=["x = 2, 3", ...], answer="x = 2, 3 (factor
as (x-2)(x-3) = 0)". correct_option() extracts the option that `answer`
starts with. Free-response items (no options, or an answer that doesn't
match any option) are excluded from mock tests -- they're still browsable
on the topic page, just not auto-gradable.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from config import MOCK_TEST_LENGTH
from models import Attempt, ContentItem, Topic, db


def correct_option(item: ContentItem) -> str | None:
    """Returns the option text that item.answer identifies as correct, or
    None if the item isn't a gradable MCQ (no options, or answer doesn't
    match any option)."""
    if not item.options or not item.answer:
        return None
    try:
        options = json.loads(item.options)
    except (TypeError, ValueError):
        return None

    answer = item.answer.strip()
    # Prefer the longest matching option, in case one option's text is a
    # prefix of another's (e.g. "5 m/s" vs "5 m/s²").
    matches = [opt for opt in options if answer.startswith(opt.strip())]
    if not matches:
        return None
    return max(matches, key=len)


def gradable_question_pool(*, subject_id: int, class_level: int, topic_id: int | None, include_premium: bool):
    """Returns the list of ContentItem rows eligible for a mock test given
    this scope and the user's premium status."""
    query = (
        ContentItem.query.join(Topic)
        .filter(
            Topic.subject_id == subject_id,
            Topic.class_level == class_level,
            ContentItem.type == "practice_question",
        )
    )
    if topic_id is not None:
        query = query.filter(Topic.id == topic_id)
    if not include_premium:
        query = query.filter(ContentItem.is_premium.is_(False))

    candidates = query.all()
    return [item for item in candidates if correct_option(item) is not None]


def start_attempt(*, user, subject_id: int, class_level: int, topic_id: int | None) -> Attempt | None:
    """Builds and persists a new Attempt with a random question pool sized
    to MOCK_TEST_LENGTH (or fewer, if the eligible pool is smaller). Returns
    None if there aren't enough eligible questions (caller should check
    gradable_question_pool()'s length against MOCK_TEST_MIN_QUESTIONS first
    to give a clear "not enough content" message rather than relying on
    this)."""
    pool = gradable_question_pool(
        subject_id=subject_id, class_level=class_level, topic_id=topic_id, include_premium=user.is_premium
    )
    if not pool:
        return None

    random.shuffle(pool)
    selected = pool[:MOCK_TEST_LENGTH]

    attempt = Attempt(
        user_id=user.id,
        subject_id=subject_id,
        class_level=class_level,
        topic_id=topic_id,
        question_ids=json.dumps([item.id for item in selected]),
        total_count=len(selected),
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def attempt_questions(attempt: Attempt) -> list[ContentItem]:
    """The attempt's questions, in the fixed order they were selected in."""
    ids = json.loads(attempt.question_ids)
    items_by_id = {item.id: item for item in ContentItem.query.filter(ContentItem.id.in_(ids)).all()}
    return [items_by_id[i] for i in ids if i in items_by_id]


def grade_attempt(attempt: Attempt, submitted_answers: dict[str, str]) -> Attempt:
    """submitted_answers is {str(question_id): selected_option_text}, as
    posted from the test-taking form. Persists answers/score/finished_at."""
    items = attempt_questions(attempt)
    correct = 0
    for item in items:
        selected = submitted_answers.get(str(item.id))
        if selected is not None and selected == correct_option(item):
            correct += 1

    attempt.answers = json.dumps(submitted_answers)
    attempt.correct_count = correct
    attempt.total_count = len(items)
    attempt.score = round(100 * correct / len(items), 1) if items else 0.0
    attempt.finished_at = datetime.now(timezone.utc)
    db.session.commit()
    return attempt


def topic_accuracy(user) -> list[dict]:
    """Per-topic accuracy across all of this user's finished attempts, for
    the /progress weak-topic view. Only meaningful for topic-scoped
    attempts (whole-subject attempts mix topics, so they're excluded here
    -- their score still counts in the overall subject stats on /progress,
    just not per-topic)."""
    finished = [a for a in user.attempts if a.finished_at is not None and a.topic_id is not None]
    by_topic: dict[int, list[float]] = {}
    for attempt in finished:
        by_topic.setdefault(attempt.topic_id, []).append(attempt.score or 0.0)

    results = []
    for topic_id, scores in by_topic.items():
        topic = db.session.get(Topic, topic_id)
        if topic is None:
            continue
        avg = sum(scores) / len(scores)
        results.append(
            {
                "topic": topic,
                "attempts": len(scores),
                "average_score": round(avg, 1),
            }
        )
    results.sort(key=lambda r: r["average_score"])
    return results
