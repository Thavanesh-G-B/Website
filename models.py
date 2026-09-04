"""Database models for the Study Library.

Schema:
    Subject   -- Math, Physics, Chemistry, Biology, English
    Topic     -- a syllabus topic within a subject + class level
                 e.g. Subject=Physics, class_level=11, name="Laws of Motion"
    ContentItem -- one piece of content under a topic: either a "concept"
                 (an explanation/summary) or a "practice_question" (with an
                 optional answer/options). Always keeps provenance
                 (source_name, source_url, license) so you always know
                 where scraped content came from. is_premium marks content
                 only visible to premium accounts -- concepts are never
                 premium; only a subset of practice questions are.
    User      -- an account, with an is_premium flag. Password hashing via
                 werkzeug (already a Flask dependency); no separate crypto
                 lib needed.
    Attempt   -- one completed or in-progress mock test: a fixed list of
                 question ids (question_ids), the user's submitted answers
                 (answers), and the resulting score once graded.
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)

    topics = db.relationship("Topic", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject {self.name}>"


class Topic(db.Model):
    __tablename__ = "topics"
    __table_args__ = (
        db.UniqueConstraint("subject_id", "class_level", "slug", name="uq_topic_subject_class_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    class_level = db.Column(db.Integer, nullable=False)  # 11 or 12
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False)

    subject = db.relationship("Subject", back_populates="topics")
    items = db.relationship("ContentItem", back_populates="topic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Topic {self.subject.name if self.subject else '?'}/{self.class_level}/{self.name}>"


class ContentItem(db.Model):
    __tablename__ = "content_items"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)

    type = db.Column(db.String(30), nullable=False)  # "concept" | "practice_question"
    title = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)  # explanation, or the question text

    # Only used for type == "practice_question"
    options = db.Column(db.Text, nullable=True)  # JSON-encoded list of choices, if MCQ
    answer = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(20), nullable=True)  # easy | medium | hard

    # Provenance -- always recorded so scraped content stays attributable.
    source_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.String(1000), nullable=True)
    license = db.Column(db.String(200), nullable=True)

    # Freemium gating. Only ever set True on practice_question rows -- see
    # module docstring. Scraped/seeded content defaults to free (False).
    is_premium = db.Column(db.Boolean, default=False, nullable=False)

    scraped_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    topic = db.relationship("Topic", back_populates="items")

    def __repr__(self):
        return f"<ContentItem {self.type}:{self.title[:40]!r}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    premium_since = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    attempts = db.relationship("Attempt", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class Attempt(db.Model):
    """One mock test: a fixed, ordered pool of practice_question ids chosen
    at start time, plus the user's answers and resulting score once graded.
    Scoped to a subject + class_level, optionally narrowed to one topic.
    """

    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    class_level = db.Column(db.Integer, nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=True)  # None = whole subject

    question_ids = db.Column(db.Text, nullable=False)  # JSON list[int], fixed order
    answers = db.Column(db.Text, nullable=True)  # JSON dict {str(question_id): selected_option}

    correct_count = db.Column(db.Integer, nullable=True)
    total_count = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=True)  # percent, 0-100; set when graded

    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="attempts")
    subject = db.relationship("Subject")
    topic = db.relationship("Topic")

    def __repr__(self):
        return f"<Attempt user={self.user_id} subject={self.subject_id} score={self.score}>"
