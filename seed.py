"""Seeds the database with a small set of original, hand-written sample
content so the site has something to show immediately -- before you've run
the scraper at all. This is NOT scraped from anywhere; it's original text
written for this project, so there are no attribution/licensing concerns.

Run:
    python seed.py
"""

from app import create_app
from models import ContentItem, Subject, Topic, db
from slugify_util import slugify

SAMPLE_DATA = [
    # (subject, class_level, topic, concept_title, concept_body,
    #  question_title, question_options, question_answer)
    (
        "Math", 11, "Quadratic Equations",
        "What is a quadratic equation?",
        "A quadratic equation is a polynomial equation of degree 2, written in the "
        "standard form ax² + bx + c = 0, where a ≠ 0. Its solutions (roots) can be "
        "found by factoring, completing the square, or the quadratic formula "
        "x = (-b ± √(b² - 4ac)) / 2a. The discriminant D = b² - 4ac tells you the "
        "nature of the roots: D > 0 gives two distinct real roots, D = 0 gives one "
        "repeated real root, and D < 0 gives two complex conjugate roots.",
        "Solve x² - 5x + 6 = 0.",
        ["x = 1, 6", "x = 2, 3", "x = -2, -3", "x = 2, -3"],
        "x = 2, 3 (factor as (x-2)(x-3) = 0)",
    ),
    (
        "Math", 12, "Applications of Derivatives",
        "Using derivatives to find maxima and minima",
        "The derivative of a function tells you its instantaneous rate of change. At a "
        "local maximum or minimum, the tangent to the curve is horizontal, so the first "
        "derivative equals zero (a 'critical point'). The second derivative test then "
        "classifies it: if f''(x) > 0 the point is a local minimum, if f''(x) < 0 it's a "
        "local maximum. This is widely used to solve optimization problems, e.g. "
        "minimizing cost or maximizing area subject to a constraint.",
        "For f(x) = x³ - 3x, find the x-value(s) of any local extrema.",
        None,
        "f'(x) = 3x² - 3 = 0 → x = ±1. f''(x) = 6x, so f''(1) = 6 > 0 (local min at x=1) "
        "and f''(-1) = -6 < 0 (local max at x=-1).",
    ),
    (
        "Physics", 11, "Laws of Motion",
        "Newton's three laws of motion",
        "First law (inertia): an object stays at rest or in uniform motion unless acted "
        "on by a net external force. Second law: the net force on an object equals its "
        "mass times acceleration, F = ma. Third law: for every action there is an equal "
        "and opposite reaction. Together these laws explain how forces cause changes in "
        "motion and are the foundation of classical mechanics.",
        "A 2 kg block is pushed with a net force of 10 N. What is its acceleration?",
        ["2 m/s²", "5 m/s²", "10 m/s²", "20 m/s²"],
        "5 m/s² (a = F/m = 10/2)",
    ),
    (
        "Physics", 12, "Current Electricity",
        "Ohm's law and electrical resistance",
        "Ohm's law states that the current through a conductor between two points is "
        "directly proportional to the voltage across those points, provided temperature "
        "stays constant: V = IR. Resistance R depends on the conductor's length (L), "
        "cross-sectional area (A), and resistivity (ρ): R = ρL/A. Resistors in series add "
        "directly (R_total = R1 + R2 + ...); in parallel their reciprocals add "
        "(1/R_total = 1/R1 + 1/R2 + ...).",
        "Two resistors of 4 Ω and 6 Ω are connected in series across a 10 V battery. "
        "What is the current in the circuit?",
        ["0.4 A", "1 A", "1.5 A", "2.5 A"],
        "1 A (R_total = 10 Ω, I = V/R = 10/10)",
    ),
    (
        "Chemistry", 11, "Some Basic Concepts of Chemistry",
        "The mole concept",
        "A mole is the SI unit for amount of substance, defined as exactly "
        "6.022×10²³ elementary entities (Avogadro's number). One mole of any substance "
        "has a mass in grams equal to its molar mass. Moles let chemists convert between "
        "the microscopic scale (atoms/molecules) and the macroscopic scale (grams) that "
        "can actually be measured on a balance.",
        "How many moles are there in 22 g of CO₂? (Molar mass of CO₂ ≈ 44 g/mol)",
        ["0.25 mol", "0.5 mol", "1 mol", "2 mol"],
        "0.5 mol (moles = mass / molar mass = 22/44)",
    ),
    (
        "Chemistry", 12, "Electrochemistry",
        "Electrochemical cells and electrode potential",
        "An electrochemical (galvanic) cell converts chemical energy into electrical "
        "energy via spontaneous redox reactions occurring at two separated electrodes "
        "connected by an external circuit and a salt bridge. The standard electrode "
        "potential (E°) measures a half-reaction's tendency to be reduced, relative to "
        "the standard hydrogen electrode (0 V). Cell potential E°cell = E°cathode - E°anode; "
        "a positive value means the reaction is spontaneous.",
        "In a Daniel cell (Zn | Zn²⁺ || Cu²⁺ | Cu), which electrode is the cathode?",
        ["Zinc electrode", "Copper electrode", "Both equally", "Neither"],
        "Copper electrode (reduction of Cu²⁺ to Cu occurs at the cathode)",
    ),
    (
        "Biology", 11, "Cell: The Unit of Life",
        "Structure of a eukaryotic cell",
        "The cell is the basic structural and functional unit of life. A eukaryotic cell "
        "has a true nucleus enclosed by a nuclear membrane, and membrane-bound organelles "
        "such as mitochondria (respiration/ATP production), the endoplasmic reticulum "
        "and Golgi apparatus (protein/lipid processing), and lysosomes (digestion). The "
        "plasma membrane, made of a phospholipid bilayer, regulates what enters and "
        "leaves the cell.",
        "Which organelle is primarily responsible for producing ATP in a eukaryotic cell?",
        ["Nucleus", "Golgi apparatus", "Mitochondrion", "Ribosome"],
        "Mitochondrion",
    ),
    (
        "Biology", 12, "Principles of Inheritance and Variation",
        "Mendel's laws of inheritance",
        "Gregor Mendel's experiments on pea plants established two key laws. The Law of "
        "Segregation: each organism carries two alleles for a trait, which separate "
        "during gamete formation so each gamete carries only one. The Law of Independent "
        "Assortment: alleles of different genes (on different chromosomes) assort "
        "independently of one another during gamete formation. A monohybrid cross "
        "between two heterozygotes typically gives a 3:1 phenotypic ratio in the F2 "
        "generation.",
        "In a monohybrid cross between two heterozygous (Tt) tall pea plants, what "
        "phenotypic ratio is expected in the offspring (T = tall, dominant)?",
        ["1:1", "3:1", "1:2:1", "9:3:3:1"],
        "3:1 (tall : short)",
    ),
    (
        "English", 11, "Parts of Speech",
        "The eight parts of speech",
        "English words are classified into eight parts of speech based on their function "
        "in a sentence: nouns (name people/places/things), pronouns (replace nouns), "
        "verbs (express action or state), adjectives (describe nouns), adverbs (modify "
        "verbs/adjectives/other adverbs), prepositions (show relationships, e.g. 'in', "
        "'on'), conjunctions (join words/clauses, e.g. 'and', 'but'), and interjections "
        "(express sudden emotion, e.g. 'Wow!'). The same word can act as different parts "
        "of speech depending on context.",
        "In the sentence 'She quickly finished her homework', what part of speech is "
        "'quickly'?",
        ["Noun", "Adjective", "Adverb", "Preposition"],
        "Adverb (it modifies the verb 'finished')",
    ),
    (
        "English", 12, "English Grammar Essentials",
        "Active and passive voice",
        "In the active voice, the subject performs the action ('The teacher explained "
        "the topic'). In the passive voice, the subject receives the action, and the "
        "performer becomes optional, introduced with 'by' ('The topic was explained by "
        "the teacher'). Passive voice is formed with a form of 'to be' plus the past "
        "participle of the main verb. It's commonly used when the doer is unknown, "
        "unimportant, or when the focus should be on the action/result rather than who "
        "did it.",
        "Convert to passive voice: 'The committee will announce the results tomorrow.'",
        None,
        "The results will be announced by the committee tomorrow.",
    ),
]


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        added = 0
        for (subject_name, class_level, topic_name, c_title, c_body,
             q_title, q_options, q_answer) in SAMPLE_DATA:

            subject = Subject.query.filter_by(name=subject_name).first()
            if subject is None:
                subject = Subject(name=subject_name, slug=slugify(subject_name))
                db.session.add(subject)
                db.session.flush()

            slug = slugify(topic_name)
            topic = Topic.query.filter_by(subject_id=subject.id, class_level=class_level, slug=slug).first()
            if topic is None:
                topic = Topic(subject_id=subject.id, class_level=class_level, name=topic_name, slug=slug)
                db.session.add(topic)
                db.session.flush()

            def add_item(**kwargs):
                nonlocal added
                exists = ContentItem.query.filter_by(
                    topic_id=topic.id, type=kwargs["type"], title=kwargs["title"]
                ).first()
                if exists:
                    return
                db.session.add(ContentItem(topic_id=topic.id, **kwargs))
                added += 1

            import json as _json

            add_item(
                type="concept", title=c_title, body=c_body,
                source_name="Study Library (sample)", license="Original content",
            )
            add_item(
                type="practice_question", title=q_title, body=q_title,
                options=_json.dumps(q_options) if q_options else None,
                answer=q_answer, difficulty="medium",
                source_name="Study Library (sample)", license="Original content",
            )

        db.session.commit()
        print(f"Seeded {added} sample content item(s). Run `python app.py` and visit http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
