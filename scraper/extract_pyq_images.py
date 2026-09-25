"""Extracts real questions (as images) + answers from official NTA JEE Main
"Question Paper" PDFs, downloaded via download_official_papers.py, and
imports them as ContentItems.

WHY IMAGES, NOT TEXT: JEE Main question papers render question stems and
MCQ options as embedded images (for anti-cheating randomization + complex
math/chemistry notation), not selectable text. Confirmed by direct
inspection of a real sample -- see commit history around this file. OCR
would be unreliable for this kind of notation, so ContentItem gained
image-based fields (body_image, option_images) instead -- see models.py.

HOW PARSING WORKS: these PDFs come from a consistent exam-platform export
format, confirmed by inspecting a real sample page-by-page with bounding
boxes. Reading each page's text+image blocks in document order (which is
already top-to-bottom reading order for this single-column layout):

    Question Number : N  Question Id : ID  Question Type : MCQ ...
    [ ... 1-2 more metadata text lines ... ]
    [STEM IMAGE]
    Options :
    <option_id_1>.
    [OPTION IMAGE 1]
    <option_id_2>.
    [OPTION IMAGE 2]
    ... (4 options total for MCQ)

Numerical ("SA" = short-answer) questions skip the Options block entirely
and instead have the answer embedded as plain text:

    Question Number : N  Question Id : ID  Question Type : SA ...
    [STEM IMAGE]
    Response Type : Numeric
    ...
    Possible Answers :
    <numeric answer, plain text>

Subject sections are marked with lines like "Mathematics Section A" /
"Mathematics Section B" (A = MCQ, B = numerical) -- tracked to tag each
question's subject as parsing proceeds.

ANSWER MATCHING: a Question Paper PDF alone tells you the 4 option IDs for
each MCQ question, but not which one is correct -- that requires the
separate "Final Answer Key" PDF for the *same exam date+shift*, which maps
Question ID -> Correct Option ID (see parse_answer_key()). Mixing a
Question Paper from one session with an Answer Key from a different one
produces meaningless IDs -- this script warns loudly if question IDs from
the two files don't overlap at all.

Usage:
    python -m scraper.extract_pyq_images \\
        --question-paper path/to/question_paper.pdf \\
        --answer-key path/to/final_answer_key.pdf \\
        --subject-map Mathematics=Math Physics=Physics Chemistry=Chemistry \\
        --class-level 12 \\
        --topic-name "JEE Main 2026 Session 2 Shift 1" \\
        --premium

Without --answer-key, questions are still extracted and stored (browsable),
but MCQ items have no known correct option, so they're excluded from
auto-graded mock tests (same rule as any other ungradable item -- see
quiz.py's gradable_question_pool()).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # PyMuPDF

QUESTION_HEADER_RE = re.compile(
    r"Question Number\s*:\s*(\d+)\s*Question Id\s*:\s*(\d+)\s*Question Type\s*:\s*(\w+)"
)
SECTION_HEADER_RE = re.compile(r"^([A-Za-z]+)\s+Section\s+([AB])$")
OPTION_ID_RE = re.compile(r"^(\d+)\.\s*$")


@dataclass
class ExtractedOption:
    option_id: str
    image_bytes: bytes
    image_ext: str


@dataclass
class ExtractedQuestion:
    question_number: int
    question_id: str
    question_type: str  # "MCQ" | "SA"
    subject: str  # e.g. "Mathematics" -- as printed in the PDF, not yet mapped to this project's Subject names
    stem_image_bytes: bytes
    stem_image_ext: str
    options: list[ExtractedOption] = field(default_factory=list)
    numeric_answer: str | None = None  # for SA (numerical) questions


def _iter_blocks(doc):
    """Yields (kind, payload) for every text line / image across the whole
    document, in reading order, with page boundaries transparent to the
    caller (a question's blocks can span two pages)."""
    for page in doc:
        d = page.get_text("dict")
        for block in d["blocks"]:
            if block["type"] == 1:
                ext = block.get("ext", "png")
                yield "image", (block.get("image"), ext)
            else:
                for line in block["lines"]:
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text:
                        yield "text", text


def parse_question_paper(pdf_path: str) -> list[ExtractedQuestion]:
    doc = fitz.open(pdf_path)
    questions: list[ExtractedQuestion] = []

    current_subject = "Unknown"
    q: ExtractedQuestion | None = None
    state = "seeking_question"  # -> seeking_stem_image -> after_stem -> seeking_option_id -> seeking_option_image
    pending_option_id = None

    def flush():
        nonlocal q
        if q is not None:
            questions.append(q)
        q = None

    for kind, payload in _iter_blocks(doc):
        if kind == "text":
            text = payload

            section_match = SECTION_HEADER_RE.match(text)
            if section_match:
                current_subject = section_match.group(1)
                continue

            header_match = QUESTION_HEADER_RE.search(text)
            if header_match:
                flush()
                q = ExtractedQuestion(
                    question_number=int(header_match.group(1)),
                    question_id=header_match.group(2),
                    question_type=header_match.group(3),
                    subject=current_subject,
                    stem_image_bytes=b"",
                    stem_image_ext="",
                )
                state = "seeking_stem_image"
                continue

            if state == "seeking_option_id":
                opt_match = OPTION_ID_RE.match(text)
                if opt_match:
                    pending_option_id = opt_match.group(1)
                    state = "seeking_option_image"
                    continue

            if state in ("after_stem",) and text == "Options :":
                state = "seeking_option_id"
                continue

            if state == "after_stem" and text.startswith("Possible Answers"):
                state = "seeking_numeric_answer"
                continue

            if state == "seeking_numeric_answer" and q is not None:
                q.numeric_answer = text
                state = "after_stem"  # answer found; stay put until next question header
                continue

            # Any other metadata line (Question Mandatory, Response Type,
            # Evaluation Required, etc.) -- ignore, keep current state.

        elif kind == "image":
            image_bytes, ext = payload
            if state == "seeking_stem_image" and q is not None:
                q.stem_image_bytes = image_bytes
                q.stem_image_ext = ext
                state = "after_stem"
            elif state == "seeking_option_image" and q is not None and pending_option_id is not None:
                q.options.append(ExtractedOption(pending_option_id, image_bytes, ext))
                pending_option_id = None
                state = "seeking_option_id"

    flush()
    return questions


def parse_answer_key(pdf_path: str) -> dict[str, str]:
    """Returns {question_id: correct_option_id_or_numeric_value}. Skips
    "DROP" (nullified) questions -- they have no correct answer."""
    doc = fitz.open(pdf_path)
    answers: dict[str, str] = {}

    # The answer key is a flat table: alternating "Question ID" / value rows
    # (see base_scraper/README discussion of its structure), repeated per
    # exam date+shift block, with a "Question ID" / "Correct Option ID"
    # header pair per subject column. We don't need to parse the headers --
    # just walk every numeric-ID-then-value pair in the whole document.
    tokens = []
    for page in doc:
        for line in page.get_text().splitlines():
            line = line.strip()
            if line:
                tokens.append(line)

    # Reconstruct (question_id, value) pairs: a "Question ID" is always an
    # 8+ digit number; the following token is its value (another number, or
    # "DROP"). Header/label tokens (non-numeric) are skipped.
    i = 0
    while i < len(tokens) - 1:
        tok = tokens[i]
        nxt = tokens[i + 1]
        if tok.isdigit() and len(tok) >= 7 and (nxt.isdigit() or nxt == "DROP"):
            if nxt != "DROP":
                answers[tok] = nxt
            i += 2
        else:
            i += 1

    return answers


def summarize(questions: list[ExtractedQuestion], answers: dict[str, str] | None):
    by_subject: dict[str, int] = {}
    mcq_count = sa_count = 0
    matched = 0
    for q in questions:
        by_subject[q.subject] = by_subject.get(q.subject, 0) + 1
        if q.question_type == "MCQ":
            mcq_count += 1
            if answers and q.question_id in answers:
                matched += 1
        else:
            sa_count += 1

    print(f"Parsed {len(questions)} questions: {mcq_count} MCQ, {sa_count} numerical (SA)")
    print(f"By subject: {by_subject}")
    if answers is not None:
        print(f"Answer key matched {matched}/{mcq_count} MCQ questions by Question ID")
        if mcq_count and matched == 0:
            print(
                "\n[WARNING] Zero MCQ questions matched the answer key -- the Question Paper "
                "and Answer Key are very likely from DIFFERENT exam sessions. Download both "
                "from the same date+shift for real answer matching."
            )


def _save_image(image_bytes: bytes, ext: str, images_dir_abs: str, images_dir_rel: str, basename: str) -> str:
    """Writes image_bytes to <images_dir_abs>/<basename>.<ext> and returns
    the path relative to static/ (images_dir_rel/<basename>.<ext>), for
    storing on ContentItem.body_image / option_images."""
    os.makedirs(images_dir_abs, exist_ok=True)
    filename = f"{basename}.{ext}"
    with open(os.path.join(images_dir_abs, filename), "wb") as f:
        f.write(image_bytes)
    return f"{images_dir_rel}/{filename}"


def import_questions(
    *,
    question_paper_path: str,
    answer_key_path: str | None,
    subject_map: dict[str, str],
    class_level: int,
    topic_name: str,
    is_premium: bool = False,
    source_name: str = "NTA Official (JEE Main)",
    source_url: str = "https://jeemain.nta.nic.in/",
    license_: str = "Official government exam paper",
) -> tuple[int, int, int]:
    """Parses question_paper_path (+ optional answer_key_path), saves images
    under static/pyq_images/<slug(topic_name)>/, and creates ContentItem
    rows (one Topic per (subject, class_level, topic_name) -- see the
    Topic-grouping decision in this module's docstring/commit history).

    Must be called inside a Flask app context (db.session available).

    Returns (inserted, skipped_existing, skipped_unmapped_subject).
    """
    # Imported here (not at module top) so this module stays importable --
    # and its parsing functions unit-testable -- without needing a full
    # Flask app context just to run `python -m scraper.extract_pyq_images
    # --dry-run`-style inspection.
    from app import create_app
    from models import ContentItem, Subject, Topic, db as _db
    from slugify_util import slugify

    questions = parse_question_paper(question_paper_path)
    answers = parse_answer_key(answer_key_path) if answer_key_path else None
    summarize(questions, answers)

    images_dir_rel_base = f"pyq_images/{slugify(topic_name)}"
    images_dir_abs_base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", images_dir_rel_base
    )

    inserted = skipped_existing = skipped_unmapped = 0
    topics_by_subject: dict[str, Topic] = {}

    for q in questions:
        project_subject_name = subject_map.get(q.subject)
        if project_subject_name is None:
            skipped_unmapped += 1
            continue

        if project_subject_name not in topics_by_subject:
            subject = Subject.query.filter_by(name=project_subject_name).first()
            if subject is None:
                subject = Subject(name=project_subject_name, slug=slugify(project_subject_name))
                _db.session.add(subject)
                _db.session.flush()
            slug = slugify(topic_name)
            topic = Topic.query.filter_by(subject_id=subject.id, class_level=class_level, slug=slug).first()
            if topic is None:
                topic = Topic(subject_id=subject.id, class_level=class_level, name=topic_name, slug=slug)
                _db.session.add(topic)
                _db.session.flush()
            topics_by_subject[project_subject_name] = topic
        topic = topics_by_subject[project_subject_name]

        title = f"{project_subject_name} Q{q.question_number} — {topic_name}"
        exists = ContentItem.query.filter_by(topic_id=topic.id, type="practice_question", title=title).first()
        if exists:
            skipped_existing += 1
            continue

        stem_path = _save_image(
            q.stem_image_bytes, q.stem_image_ext, images_dir_abs_base, images_dir_rel_base, f"{q.question_id}_stem"
        )

        if q.question_type == "MCQ" and q.options:
            option_ids = [opt.option_id for opt in q.options]
            option_image_paths = [
                _save_image(
                    opt.image_bytes, opt.image_ext, images_dir_abs_base, images_dir_rel_base,
                    f"{q.question_id}_opt{i}",
                )
                for i, opt in enumerate(q.options)
            ]
            correct_id = answers.get(q.question_id) if answers else None
            answer = correct_id if (correct_id and correct_id in option_ids) else None
            options_json = json.dumps(option_ids)
            option_images_json = json.dumps(option_image_paths)
        else:
            # Numerical (SA) question -- answer is embedded in the paper
            # itself, no external answer key needed, and there's nothing to
            # render as option images.
            options_json = None
            option_images_json = None
            answer = q.numeric_answer

        _db.session.add(
            ContentItem(
                topic_id=topic.id,
                type="practice_question",
                title=title,
                body=f"{project_subject_name} PYQ — {topic_name} (Question {q.question_number})",
                body_image=stem_path,
                options=options_json,
                option_images=option_images_json,
                answer=answer,
                is_premium=is_premium,
                source_name=source_name,
                source_url=source_url,
                license=license_,
            )
        )
        inserted += 1

    _db.session.commit()
    print(f"\nImported {inserted} question(s); {skipped_existing} already existed; {skipped_unmapped} had an unmapped subject.")
    return inserted, skipped_existing, skipped_unmapped


def _parse_subject_map(pairs: list[str]) -> dict[str, str]:
    result = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if not value:
            raise argparse.ArgumentTypeError(f"--subject-map entries must be KEY=VALUE, got {pair!r}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question-paper", required=True)
    parser.add_argument("--answer-key", default=None, help="Must be from the SAME exam date+shift as --question-paper")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize only -- don't write to the DB")
    parser.add_argument(
        "--subject-map", nargs="+", default=["Mathematics=Math", "Physics=Physics", "Chemistry=Chemistry"],
        help="PDF subject label=project Subject name pairs, e.g. Mathematics=Math",
    )
    parser.add_argument("--class-level", type=int, choices=[11, 12], default=12)
    parser.add_argument("--topic-name", required=False, help="Required unless --dry-run")
    parser.add_argument("--premium", action="store_true", help="Mark imported questions is_premium=True (default: free)")
    parser.add_argument("--source-name", default="NTA Official (JEE Main)")
    parser.add_argument("--source-url", default="https://jeemain.nta.nic.in/")
    parser.add_argument("--license", dest="license_", default="Official government exam paper")
    args = parser.parse_args()

    if args.dry_run:
        questions = parse_question_paper(args.question_paper)
        answers = parse_answer_key(args.answer_key) if args.answer_key else None
        summarize(questions, answers)
        return

    if not args.topic_name:
        parser.error("--topic-name is required unless --dry-run")

    from app import create_app

    app = create_app()
    with app.app_context():
        import_questions(
            question_paper_path=args.question_paper,
            answer_key_path=args.answer_key,
            subject_map=_parse_subject_map(args.subject_map),
            class_level=args.class_level,
            topic_name=args.topic_name,
            is_premium=args.premium,
            source_name=args.source_name,
            source_url=args.source_url,
            license_=args.license_,
        )


if __name__ == "__main__":
    main()
