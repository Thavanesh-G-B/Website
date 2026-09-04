"""Configuration for the Study Library app.

Everything runs locally: a SQLite database file under data/, no external
services required to browse the site. The scraper needs internet access
only when you actually run it.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")


class Config:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")


# Subjects and class levels the whole app is built around. Keep this as the
# single source of truth so scraper configs and UI stay in sync.
SUBJECTS = ["Math", "Physics", "Chemistry", "Biology", "English"]
CLASS_LEVELS = [11, 12]
CONTENT_TYPES = ["concept", "practice_question"]

# --- Freemium / mock-test settings -----------------------------------------
# Concepts are always free (they're Wikipedia-sourced, so charging for them
# makes no sense). Practice questions can be individually flagged
# is_premium=True; free accounts simply never see those in browsing or in
# mock tests. See models.User.is_premium and quiz.py.
MOCK_TEST_LENGTH = 10  # questions per generated mock test (capped by pool size)
MOCK_TEST_MIN_QUESTIONS = 2  # below this, refuse to start a test -- not enough content yet
WEAK_TOPIC_ACCURACY_THRESHOLD = 0.6  # topics below this average score are flagged on /progress
