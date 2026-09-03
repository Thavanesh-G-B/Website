"""Study Library -- a local website for browsing scraped/curated Class 11 &
12 study material (concepts + practice questions) across Math, Physics,
Chemistry, Biology and English.

Run locally:
    pip install -r requirements.txt
    python seed.py             # creates the DB and adds a handful of sample items
    python app.py               # starts the site at http://127.0.0.1:5000

Populate it for real with the scraper:
    python -m scraper.run_scraper
"""

import json

from flask import Flask, abort, render_template, request

from config import CLASS_LEVELS, Config, SUBJECTS
from models import ContentItem, Subject, Topic, db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    @app.route("/")
    def index():
        subjects = Subject.query.order_by(Subject.name).all()
        # Count content items per (subject, class_level) so the home page
        # shows how much material exists before clicking in.
        counts = {}
        for subject in subjects:
            for class_level in CLASS_LEVELS:
                n = (
                    ContentItem.query.join(Topic)
                    .filter(Topic.subject_id == subject.id, Topic.class_level == class_level)
                    .count()
                )
                counts[(subject.id, class_level)] = n
        return render_template(
            "index.html", subjects=subjects, class_levels=CLASS_LEVELS, counts=counts, all_subjects=SUBJECTS
        )

    @app.route("/subject/<slug>/<int:class_level>")
    def subject_view(slug, class_level):
        subject = Subject.query.filter_by(slug=slug).first_or_404()
        if class_level not in CLASS_LEVELS:
            abort(404)
        topics = (
            Topic.query.filter_by(subject_id=subject.id, class_level=class_level)
            .order_by(Topic.name)
            .all()
        )
        topic_counts = {t.id: len(t.items) for t in topics}
        return render_template(
            "subject.html", subject=subject, class_level=class_level, topics=topics, topic_counts=topic_counts
        )

    @app.route("/topic/<int:topic_id>")
    def topic_view(topic_id):
        topic = Topic.query.get_or_404(topic_id)
        item_type = request.args.get("type")
        query = ContentItem.query.filter_by(topic_id=topic.id)
        if item_type in ("concept", "practice_question"):
            query = query.filter_by(type=item_type)
        items = query.order_by(ContentItem.type, ContentItem.id).all()
        for item in items:
            item.options_list = json.loads(item.options) if item.options else None
        return render_template("topic.html", topic=topic, items=items, active_type=item_type)

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        results = []
        if q:
            like = f"%{q}%"
            results = (
                ContentItem.query.filter(
                    db.or_(ContentItem.title.ilike(like), ContentItem.body.ilike(like))
                )
                .join(Topic)
                .order_by(ContentItem.type, ContentItem.title)
                .limit(200)
                .all()
            )
        return render_template("search.html", q=q, results=results)

    @app.context_processor
    def inject_globals():
        return {"all_subjects": SUBJECTS, "class_levels": CLASS_LEVELS}

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
