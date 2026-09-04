"""Study Library -- a local website for browsing scraped/curated Class 11 &
12 study material (concepts + practice questions) across Math, Physics,
Chemistry, Biology and English, with a freemium layer: accounts, a premium
practice-question tier, auto-graded mock tests, and a progress dashboard.

Run locally:
    pip install -r requirements.txt
    python seed.py             # creates the DB and adds sample items (some free, some premium)
    python app.py               # starts the site at http://127.0.0.1:5000

Populate it for real with the scraper:
    python -m scraper.run_scraper

NOTE on payments: there is no real payment gateway wired in. /upgrade's
"activate" button is a dev-mode stand-in that just flips User.is_premium --
see the comment on that route for what a real launch needs.
"""

import json
from datetime import datetime, timezone

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

import quiz
from config import (
    CLASS_LEVELS,
    Config,
    MOCK_TEST_LENGTH,
    MOCK_TEST_MIN_QUESTIONS,
    SUBJECTS,
    WEAK_TOPIC_ACCURACY_THRESHOLD,
)
from models import Attempt, ContentItem, Subject, Topic, User, db


def create_app(test_config: dict | None = None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        # Applied before db.init_app() so tests can point at an isolated DB
        # (e.g. sqlite:///:memory:) instead of the real data/app.db -- see
        # tests/test_quiz.py.
        app.config.update(test_config)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Log in to continue."
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---------------------------------------------------------------- browse

    @app.route("/")
    def index():
        subjects = Subject.query.order_by(Subject.name).all()
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

        unlocked = current_user.is_authenticated and current_user.is_premium
        for item in items:
            # Premium gating: concepts are never premium (is_premium is only
            # ever set on practice_question rows), so this only hides body/
            # options/answer on locked practice questions -- the title still
            # shows so free users know the content exists.
            item.locked = item.is_premium and not unlocked
            item.options_list = None if item.locked else (json.loads(item.options) if item.options else None)

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
        unlocked = current_user.is_authenticated and current_user.is_premium
        for item in results:
            item.locked = item.is_premium and not unlocked
        return render_template("search.html", q=q, results=results)

    # ------------------------------------------------------------------ auth

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not email or "@" not in email:
                flash("Enter a valid email address.")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.")
            elif User.query.filter_by(email=email).first() is not None:
                flash("An account with that email already exists.")
            else:
                user = User(email=email, password_hash=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Account created.")
                return redirect(url_for("index"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user is not None and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(request.args.get("next") or url_for("index"))
            flash("Incorrect email or password.")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # --------------------------------------------------------------- upgrade

    @app.route("/upgrade")
    def upgrade():
        return render_template("upgrade.html")

    @app.route("/upgrade/activate", methods=["POST"])
    @login_required
    def upgrade_activate():
        # DEV-MODE STAND-IN. There is no payment gateway wired in here --
        # this just flips the flag a real checkout webhook would flip. To
        # go live, put a real payment provider (Stripe/Razorpay/etc.) in
        # front of this: create a Checkout Session in a new route, and only
        # set is_premium=True from that provider's webhook after it
        # confirms payment succeeded -- never directly from a client POST
        # like this one, or anyone could grant themselves premium for free.
        current_user.is_premium = True
        current_user.premium_since = datetime.now(timezone.utc)
        db.session.commit()
        flash("Premium activated (dev mode -- no payment was taken).")
        return redirect(url_for("upgrade"))

    @app.route("/upgrade/cancel", methods=["POST"])
    @login_required
    def upgrade_cancel():
        current_user.is_premium = False
        db.session.commit()
        flash("Premium turned off.")
        return redirect(url_for("upgrade"))

    # ----------------------------------------------------------- mock tests

    @app.route("/practice-test")
    @login_required
    def practice_test_form():
        subjects = Subject.query.order_by(Subject.name).all()
        topics = Topic.query.order_by(Topic.name).all()
        topics_json = [
            {"id": t.id, "name": t.name, "subject_id": t.subject_id, "class_level": t.class_level}
            for t in topics
        ]
        return render_template(
            "practice_test_form.html", subjects=subjects, class_levels=CLASS_LEVELS, topics_json=topics_json
        )

    @app.route("/practice-test/start", methods=["POST"])
    @login_required
    def practice_test_start():
        subject_id = request.form.get("subject_id", type=int)
        class_level = request.form.get("class_level", type=int)
        topic_id = request.form.get("topic_id", type=int) or None

        subject = Subject.query.get_or_404(subject_id)
        if class_level not in CLASS_LEVELS:
            abort(404)

        pool = quiz.gradable_question_pool(
            subject_id=subject.id, class_level=class_level, topic_id=topic_id,
            include_premium=current_user.is_premium,
        )
        if len(pool) < MOCK_TEST_MIN_QUESTIONS:
            flash(
                f"Not enough auto-gradable practice questions here yet "
                f"({len(pool)} available, need at least {MOCK_TEST_MIN_QUESTIONS})."
                + ("" if current_user.is_premium else " Premium unlocks more questions per topic.")
            )
            return redirect(url_for("practice_test_form"))

        attempt = quiz.start_attempt(
            user=current_user, subject_id=subject.id, class_level=class_level, topic_id=topic_id
        )
        return redirect(url_for("practice_test_take", attempt_id=attempt.id))

    @app.route("/practice-test/<int:attempt_id>", methods=["GET", "POST"])
    @login_required
    def practice_test_take(attempt_id):
        attempt = Attempt.query.get_or_404(attempt_id)
        if attempt.user_id != current_user.id:
            abort(403)
        if attempt.finished_at is not None:
            return redirect(url_for("practice_test_result", attempt_id=attempt.id))

        items = quiz.attempt_questions(attempt)
        for item in items:
            item.options_list = json.loads(item.options) if item.options else []

        if request.method == "POST":
            submitted = {
                str(item.id): request.form.get(f"question-{item.id}", "").strip()
                for item in items
            }
            quiz.grade_attempt(attempt, submitted)
            return redirect(url_for("practice_test_result", attempt_id=attempt.id))

        return render_template("practice_test_take.html", attempt=attempt, items=items)

    @app.route("/practice-test/<int:attempt_id>/result")
    @login_required
    def practice_test_result(attempt_id):
        attempt = Attempt.query.get_or_404(attempt_id)
        if attempt.user_id != current_user.id:
            abort(403)
        if attempt.finished_at is None:
            return redirect(url_for("practice_test_take", attempt_id=attempt.id))

        items = quiz.attempt_questions(attempt)
        submitted = json.loads(attempt.answers) if attempt.answers else {}
        rows = []
        for item in items:
            options = json.loads(item.options) if item.options else []
            correct = quiz.correct_option(item)
            selected = submitted.get(str(item.id))
            rows.append(
                {
                    "item": item,
                    "options": options,
                    "correct": correct,
                    "selected": selected,
                    "is_correct": selected == correct,
                }
            )
        return render_template("practice_test_result.html", attempt=attempt, rows=rows)

    # ----------------------------------------------------------------- progress

    @app.route("/progress")
    @login_required
    def progress():
        attempts = (
            Attempt.query.filter_by(user_id=current_user.id)
            .filter(Attempt.finished_at.isnot(None))
            .order_by(Attempt.finished_at.desc())
            .all()
        )

        subject_stats = {}
        for attempt in attempts:
            s = subject_stats.setdefault(attempt.subject_id, {"subject": attempt.subject, "scores": []})
            s["scores"].append(attempt.score or 0.0)
        for s in subject_stats.values():
            s["average"] = round(sum(s["scores"]) / len(s["scores"]), 1)
            s["count"] = len(s["scores"])

        weak_topics = [
            row for row in quiz.topic_accuracy(current_user)
            if row["average_score"] < 100 * WEAK_TOPIC_ACCURACY_THRESHOLD
        ]

        return render_template(
            "progress.html",
            attempts=attempts,
            subject_stats=list(subject_stats.values()),
            weak_topics=weak_topics,
            weak_threshold=WEAK_TOPIC_ACCURACY_THRESHOLD,
        )

    @app.context_processor
    def inject_globals():
        return {"all_subjects": SUBJECTS, "class_levels": CLASS_LEVELS, "mock_test_length": MOCK_TEST_LENGTH}

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
