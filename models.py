"""Database models for the Study Library.

Schema:
    Subject   -- Math, Physics, Chemistry, Biology, English
    Topic     -- a syllabus topic within a subject + class level
                 e.g. Subject=Physics, class_level=11, name="Laws of Motion"
    ContentItem -- one piece of content under a topic: either a "concept"
                 (an explanation/summary) or a "practice_question" (with an
                 optional answer/options). Always keeps provenance
                 (source_name, source_url, license) so you always know
                 where scraped content came from.
"""

from datetime import datetime, timezone

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

    scraped_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    topic = db.relationship("Topic", back_populates="items")

    def __repr__(self):
        return f"<ContentItem {self.type}:{self.title[:40]!r}>"
