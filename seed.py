"""Seeds the database with a small set of original, hand-written sample
content so the site has something to show immediately -- before you've run
the scraper at all. This is NOT scraped from anywhere; it's original text
written for this project, so there are no attribution/licensing concerns.

Run:
    python seed.py
"""

import json

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

# A second free MCQ per topic above, so the free question pool per topic is
# 2 (SAMPLE_DATA's + this one) -- combined with the 1 premium question below
# that's enough content for a premium mock test (>= MOCK_TEST_MIN_QUESTIONS)
# right out of seed.py, without needing the scraper to add more first.
# (subject, class_level, topic, question_title, options, answer)
EXTRA_FREE_QUESTIONS = [
    (
        "Math", 11, "Quadratic Equations",
        "What are the roots of x² - 9 = 0?",
        ["x = 3, -3", "x = 9, -9", "x = 3 only", "No real roots"],
        "x = 3, -3 (difference of squares: (x-3)(x+3) = 0)",
    ),
    (
        "Math", 12, "Applications of Derivatives",
        "What is the derivative of f(x) = x²?",
        ["x", "2x", "x²", "2"],
        "2x (power rule: d/dx xⁿ = nxⁿ⁻¹)",
    ),
    (
        "Physics", 11, "Laws of Motion",
        "What is the SI unit of momentum?",
        ["kg·m/s", "kg·m/s²", "Joule", "Watt"],
        "kg·m/s (momentum = mass × velocity)",
    ),
    (
        "Physics", 12, "Current Electricity",
        "What is the power dissipated in a 10 Ω resistor carrying 2 A?",
        ["20 W", "40 W", "5 W", "200 W"],
        "40 W (P = I²R = 2² × 10)",
    ),
    (
        "Chemistry", 11, "Some Basic Concepts of Chemistry",
        "Which law states that matter can neither be created nor destroyed in a chemical reaction?",
        ["Law of conservation of mass", "Law of definite proportions", "Avogadro's law", "Law of multiple proportions"],
        "Law of conservation of mass (total mass of reactants equals total mass of products)",
    ),
    (
        "Chemistry", 12, "Electrochemistry",
        "What is the SI unit of electrode potential?",
        ["Volt", "Ampere", "Ohm", "Coulomb"],
        "Volt (electrode potential is measured in volts)",
    ),
    (
        "Biology", 11, "Cell: The Unit of Life",
        "What structure regulates the entry and exit of substances in a cell?",
        ["Cell wall", "Plasma membrane", "Nucleus", "Cytoplasm"],
        "Plasma membrane (it selectively controls what enters and leaves the cell)",
    ),
    (
        "Biology", 12, "Principles of Inheritance and Variation",
        "What term describes the observable physical characteristics resulting from a genotype?",
        ["Genotype", "Phenotype", "Allele", "Locus"],
        "Phenotype (the observable expression of the genotype)",
    ),
    (
        "English", 11, "Parts of Speech",
        "In 'She sings beautifully', which word is the verb?",
        ["She", "Sings", "Beautifully", "None of these"],
        "Sings (it expresses the action)",
    ),
    (
        "English", 12, "English Grammar Essentials",
        "What tense is used in 'She has finished her homework'?",
        ["Simple past", "Present perfect", "Past perfect", "Simple present"],
        "Present perfect (has/have + past participle)",
    ),
]

# One extra, harder MCQ per topic above, gated behind is_premium -- this is
# what /upgrade actually sells: a deeper practice-question bank, not the
# (freely available anyway) concept explanations. Each answer is written as
# "<exact option text>(optional explanation)" so quiz.correct_option() can
# auto-grade it -- see that module's docstring.
# (subject, class_level, topic, question_title, options, answer)
PREMIUM_QUESTIONS = [
    (
        "Math", 11, "Quadratic Equations",
        "For ax² + bx + c = 0, if the discriminant D = 0, what can you say about the roots?",
        ["Two distinct real roots", "One repeated real root", "Two complex roots", "Cannot be determined"],
        "One repeated real root (D = 0 gives a repeated real root)",
    ),
    (
        "Math", 12, "Applications of Derivatives",
        "What does a positive second derivative at a critical point indicate?",
        ["Local maximum", "Local minimum", "Point of inflection", "Undefined"],
        "Local minimum (f''(x) > 0 indicates a local minimum)",
    ),
    (
        "Physics", 11, "Laws of Motion",
        "Which of Newton's laws best explains how a rocket propels itself forward?",
        ["First law", "Second law", "Third law", "Law of gravitation"],
        "Third law (the expelled exhaust gas exerts an equal and opposite reaction force on the rocket)",
    ),
    (
        "Physics", 12, "Current Electricity",
        "Two resistors of 4 Ω and 6 Ω are connected in parallel. What is the equivalent resistance?",
        ["10 Ω", "2.4 Ω", "1.5 Ω", "24 Ω"],
        "2.4 Ω (1/R = 1/4 + 1/6 = 5/12, so R = 12/5 = 2.4 Ω)",
    ),
    (
        "Chemistry", 11, "Some Basic Concepts of Chemistry",
        "What is the molar mass of water (H₂O), in g/mol?",
        ["16", "18", "20", "22"],
        "18 (2×1 for hydrogen + 16 for oxygen = 18)",
    ),
    (
        "Chemistry", 12, "Electrochemistry",
        "In an electrochemical cell, oxidation always occurs at which electrode?",
        ["Cathode", "Anode", "Both electrodes", "Neither electrode"],
        "Anode (oxidation always occurs at the anode, by definition)",
    ),
    (
        "Biology", 11, "Cell: The Unit of Life",
        "Which organelle is sometimes called the 'suicide bag' of the cell?",
        ["Ribosome", "Lysosome", "Golgi apparatus", "Mitochondrion"],
        "Lysosome (its digestive enzymes can break down the cell itself if released)",
    ),
    (
        "Biology", 12, "Principles of Inheritance and Variation",
        "A dihybrid cross between two heterozygous parents (RrYy × RrYy) gives what "
        "phenotypic ratio in the F2 generation, assuming independent assortment?",
        ["3:1", "1:2:1", "9:3:3:1", "1:1:1:1"],
        "9:3:3:1 (the classic dihybrid ratio under independent assortment)",
    ),
    (
        "English", 11, "Parts of Speech",
        "In the sentence 'The bright red car sped past', which word is functioning as an adjective?",
        ["Sped", "Bright", "Past", "Car"],
        "Bright (it describes the noun 'car', along with 'red')",
    ),
    (
        "English", 12, "English Grammar Essentials",
        "Which sentence is correctly written in the passive voice?",
        [
            "The dog chased the cat.",
            "The cat was chased by the dog.",
            "The cat chases the dog.",
            "Chasing the cat, the dog ran.",
        ],
        "The cat was chased by the dog. (the subject 'the cat' receives the action)",
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

            add_item(
                type="concept", title=c_title, body=c_body,
                source_name="Study Library (sample)", license="Original content",
            )
            add_item(
                type="practice_question", title=q_title, body=q_title,
                options=json.dumps(q_options) if q_options else None,
                answer=q_answer, difficulty="medium",
                source_name="Study Library (sample)", license="Original content",
            )

        def add_extra_question(rows, *, is_premium, difficulty, source_name):
            nonlocal added
            for (subject_name, class_level, topic_name, q_title, q_options, q_answer) in rows:
                subject = Subject.query.filter_by(name=subject_name).first()
                topic = Topic.query.filter_by(
                    subject_id=subject.id, class_level=class_level, slug=slugify(topic_name)
                ).first()
                if topic is None:
                    continue  # topic wasn't in SAMPLE_DATA above -- nothing to attach this to

                exists = ContentItem.query.filter_by(
                    topic_id=topic.id, type="practice_question", title=q_title
                ).first()
                if exists:
                    continue
                db.session.add(
                    ContentItem(
                        topic_id=topic.id, type="practice_question", title=q_title, body=q_title,
                        options=json.dumps(q_options), answer=q_answer, difficulty=difficulty,
                        is_premium=is_premium, source_name=source_name, license="Original content",
                    )
                )
                added += 1

        add_extra_question(
            EXTRA_FREE_QUESTIONS, is_premium=False, difficulty="medium",
            source_name="Study Library (sample)",
        )
        add_extra_question(
            PREMIUM_QUESTIONS, is_premium=True, difficulty="hard",
            source_name="Study Library (sample, premium)",
        )

        db.session.commit()
        print(f"Seeded {added} sample content item(s). Run `python app.py` and visit http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
