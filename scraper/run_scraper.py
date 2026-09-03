"""CLI entry point for running the scraper and populating the local database.

Examples:
    # Scrape everything in sources.json
    python -m scraper.run_scraper

    # Only Physics, class 11
    python -m scraper.run_scraper --subject Physics --class-level 11

    # Only concepts (skip practice-question jobs)
    python -m scraper.run_scraper --type concept

    # See what would run without touching the network or DB
    python -m scraper.run_scraper --dry-run

    # Re-fetch even if a cached copy of the page/API response exists
    python -m scraper.run_scraper --no-cache
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running as `python scraper/run_scraper.py` in addition to `-m`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import base_scraper
from scraper.base_scraper import RobotsDisallowed, ScrapeError
from scraper.registry import get_scraper

SOURCES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")


def load_jobs(path: str = SOURCES_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    return [j for j in jobs if not j.get("_disabled")]


def filter_jobs(jobs, *, subject=None, class_level=None, type_=None, topic=None):
    def matches(job):
        if subject and job["subject"].lower() != subject.lower():
            return False
        if class_level and job["class_level"] != class_level:
            return False
        if type_ and job["type"] != type_:
            return False
        if topic and topic.lower() not in job["topic"].lower():
            return False
        return True

    return [j for j in jobs if matches(j)]


def get_or_create_subject(db, models, name: str):
    from slugify_util import slugify

    subject = models.Subject.query.filter_by(name=name).first()
    if subject is None:
        subject = models.Subject(name=name, slug=slugify(name))
        db.session.add(subject)
        db.session.flush()
    return subject


def get_or_create_topic(db, models, subject, class_level: int, name: str):
    from slugify_util import slugify

    slug = slugify(name)
    topic = models.Topic.query.filter_by(subject_id=subject.id, class_level=class_level, slug=slug).first()
    if topic is None:
        topic = models.Topic(subject_id=subject.id, class_level=class_level, name=name, slug=slug)
        db.session.add(topic)
        db.session.flush()
    return topic


def upsert_item(db, models, topic, item) -> bool:
    """Returns True if a new row was inserted, False if it already existed."""
    existing = models.ContentItem.query.filter_by(
        topic_id=topic.id, type=item.type, title=item.title
    ).first()
    if existing is not None:
        return False

    row = models.ContentItem(
        topic_id=topic.id,
        type=item.type,
        title=item.title,
        body=item.body,
        options=json.dumps(item.options) if item.options else None,
        answer=item.answer,
        difficulty=item.difficulty,
        source_name=item.source_name,
        source_url=item.source_url,
        license=item.license,
    )
    db.session.add(row)
    return True


def run(jobs, *, dry_run: bool = False, use_cache: bool = True):
    if dry_run:
        print(f"[dry-run] would run {len(jobs)} job(s):")
        for j in jobs:
            print(f"  - {j['subject']} / class {j['class_level']} / {j['topic']} "
                  f"({j['type']} via {j['source']})")
        return

    # Import here so --dry-run and --help don't need Flask/DB set up.
    from app import create_app
    import models as models_module

    app = create_app()
    with app.app_context():
        db = models_module.db
        db.create_all()

        inserted = 0
        skipped_existing = 0
        failed = 0

        for job in jobs:
            label = f"{job['subject']}/{job['class_level']}/{job['topic']} ({job['source']})"
            try:
                scraper_fn = get_scraper(job["source"])
                items = scraper_fn(job) if use_cache else _run_without_cache(scraper_fn, job)
            except RobotsDisallowed as exc:
                print(f"[SKIP: robots.txt] {label}: {exc}")
                failed += 1
                continue
            except ScrapeError as exc:
                print(f"[FAIL] {label}: {exc}")
                failed += 1
                continue
            except Exception as exc:  # noqa: BLE001 - keep the run going on one bad job
                print(f"[FAIL: unexpected] {label}: {exc}")
                failed += 1
                continue

            subject = get_or_create_subject(db, models_module, job["subject"])
            topic = get_or_create_topic(db, models_module, subject, job["class_level"], job["topic"])

            for item in items:
                if upsert_item(db, models_module, topic, item):
                    inserted += 1
                    print(f"[OK] {label}: added {item.type!r} {item.title[:60]!r}")
                else:
                    skipped_existing += 1

        db.session.commit()
        print(f"\nDone. inserted={inserted} skipped_existing={skipped_existing} failed={failed}")


def _run_without_cache(scraper_fn, job):
    # Blow away any cached response for this job's URL(s) by disabling cache
    # reads for the duration of this single call. Simpler than threading a
    # use_cache flag through every scraper function.
    original_fetch = base_scraper.fetch

    def fetch_no_cache(url, **kwargs):
        kwargs["use_cache"] = False
        return original_fetch(url, **kwargs)

    base_scraper.fetch = fetch_no_cache
    try:
        return scraper_fn(job)
    finally:
        base_scraper.fetch = original_fetch


def main():
    parser = argparse.ArgumentParser(description="Scrape educational content into the local Study Library DB.")
    parser.add_argument("--subject", help="Only run jobs for this subject (e.g. Physics)")
    parser.add_argument("--class-level", type=int, choices=[11, 12], help="Only run jobs for this class level")
    parser.add_argument("--type", dest="type_", choices=["concept", "practice_question"], help="Only run jobs of this type")
    parser.add_argument("--topic", help="Only run jobs whose topic name contains this substring")
    parser.add_argument("--dry-run", action="store_true", help="List matching jobs without fetching or writing anything")
    parser.add_argument("--no-cache", action="store_true", help="Ignore any cached copies and re-fetch from the network")
    parser.add_argument("--sources", default=SOURCES_PATH, help="Path to sources.json")
    args = parser.parse_args()

    jobs = load_jobs(args.sources)
    jobs = filter_jobs(jobs, subject=args.subject, class_level=args.class_level, type_=args.type_, topic=args.topic)

    if not jobs:
        print("No jobs matched those filters.")
        return

    run(jobs, dry_run=args.dry_run, use_cache=not args.no_cache)


if __name__ == "__main__":
    main()
