"""Generates sources.json from the curated topic list below.

Run this whenever you want to regenerate sources.json from scratch (e.g.
after editing TOPICS in this file):

    python -m scraper.build_sources

sources.json itself is the file run_scraper.py actually reads, and it's
fine to hand-edit it afterwards (e.g. to add a generic_html job for a
specific practice-question site) -- just don't re-run this script
afterwards without folding your edits back in here, or they'll be
overwritten.

Each entry maps one syllabus topic to a Wikipedia article used to
populate a "concept" ContentItem. Wikipedia article titles are curated by
hand below to match NCERT-style Class 11/12 syllabi as closely as
Wikipedia's own article structure allows.
"""

import json
import os

# (subject, class_level, topic_name, wikipedia_title)
TOPICS = [
    # ---------------- Math ----------------
    ("Math", 11, "Sets", "Set (mathematics)"),
    ("Math", 11, "Relations and Functions", "Function (mathematics)"),
    ("Math", 11, "Trigonometric Functions", "Trigonometric functions"),
    ("Math", 11, "Complex Numbers", "Complex number"),
    ("Math", 11, "Linear Inequalities", "Linear inequality"),
    ("Math", 11, "Permutations and Combinations", "Permutation"),
    ("Math", 11, "Binomial Theorem", "Binomial theorem"),
    ("Math", 11, "Sequences and Series", "Arithmetic progression"),
    ("Math", 11, "Straight Lines", "Line (geometry)"),
    ("Math", 11, "Conic Sections", "Conic section"),
    ("Math", 11, "Limits and Derivatives", "Derivative"),
    ("Math", 12, "Inverse Trigonometric Functions", "Inverse trigonometric functions"),
    ("Math", 12, "Matrices", "Matrix (mathematics)"),
    ("Math", 12, "Determinants", "Determinant"),
    ("Math", 12, "Continuity and Differentiability", "Continuous function"),
    ("Math", 12, "Applications of Derivatives", "Derivative test"),
    ("Math", 12, "Integrals", "Integral"),
    ("Math", 12, "Differential Equations", "Differential equation"),
    ("Math", 12, "Vector Algebra", "Euclidean vector"),
    ("Math", 12, "Three Dimensional Geometry", "Analytic geometry"),
    ("Math", 12, "Probability", "Probability"),

    # ---------------- Physics ----------------
    ("Physics", 11, "Units and Measurement", "International System of Units"),
    ("Physics", 11, "Motion in a Straight Line", "Kinematics"),
    ("Physics", 11, "Laws of Motion", "Newton's laws of motion"),
    ("Physics", 11, "Work, Energy and Power", "Work (physics)"),
    ("Physics", 11, "Rotational Motion", "Angular momentum"),
    ("Physics", 11, "Gravitation", "Gravity"),
    ("Physics", 11, "Mechanical Properties of Solids", "Elasticity (physics)"),
    ("Physics", 11, "Thermodynamics", "Thermodynamics"),
    ("Physics", 11, "Kinetic Theory", "Kinetic theory of gases"),
    ("Physics", 11, "Oscillations", "Oscillation"),
    ("Physics", 11, "Waves", "Wave"),
    ("Physics", 12, "Electric Charges and Fields", "Electric charge"),
    ("Physics", 12, "Electrostatic Potential and Capacitance", "Electric potential"),
    ("Physics", 12, "Current Electricity", "Electric current"),
    ("Physics", 12, "Moving Charges and Magnetism", "Magnetic field"),
    ("Physics", 12, "Electromagnetic Induction", "Electromagnetic induction"),
    ("Physics", 12, "Alternating Current", "Alternating current"),
    ("Physics", 12, "Electromagnetic Waves", "Electromagnetic radiation"),
    ("Physics", 12, "Ray Optics", "Geometrical optics"),
    ("Physics", 12, "Wave Optics", "Physical optics"),
    ("Physics", 12, "Dual Nature of Radiation and Matter", "Wave-particle duality"),
    ("Physics", 12, "Atoms", "Bohr model"),
    ("Physics", 12, "Nuclei", "Atomic nucleus"),
    ("Physics", 12, "Semiconductor Electronics", "Semiconductor"),

    # ---------------- Chemistry ----------------
    ("Chemistry", 11, "Some Basic Concepts of Chemistry", "Stoichiometry"),
    ("Chemistry", 11, "Structure of Atom", "Atomic theory"),
    ("Chemistry", 11, "Classification of Elements and Periodicity", "Periodic table"),
    ("Chemistry", 11, "Chemical Bonding and Molecular Structure", "Chemical bond"),
    ("Chemistry", 11, "States of Matter", "State of matter"),
    ("Chemistry", 11, "Thermodynamics", "Chemical thermodynamics"),
    ("Chemistry", 11, "Equilibrium", "Chemical equilibrium"),
    ("Chemistry", 11, "Redox Reactions", "Redox"),
    ("Chemistry", 11, "Hydrogen", "Hydrogen"),
    ("Chemistry", 11, "Organic Chemistry Basics", "Organic chemistry"),
    ("Chemistry", 11, "Hydrocarbons", "Hydrocarbon"),
    ("Chemistry", 12, "Solid State", "Crystal structure"),
    ("Chemistry", 12, "Solutions", "Solution (chemistry)"),
    ("Chemistry", 12, "Electrochemistry", "Electrochemistry"),
    ("Chemistry", 12, "Chemical Kinetics", "Chemical kinetics"),
    ("Chemistry", 12, "Surface Chemistry", "Colloid"),
    ("Chemistry", 12, "d and f Block Elements", "Transition metal"),
    ("Chemistry", 12, "Coordination Compounds", "Coordination complex"),
    ("Chemistry", 12, "Haloalkanes and Haloarenes", "Haloalkane"),
    ("Chemistry", 12, "Alcohols, Phenols and Ethers", "Alcohol"),
    ("Chemistry", 12, "Aldehydes, Ketones and Carboxylic Acids", "Aldehyde"),
    ("Chemistry", 12, "Amines", "Amine"),
    ("Chemistry", 12, "Biomolecules", "Biomolecule"),
    ("Chemistry", 12, "Polymers", "Polymer"),

    # ---------------- Biology ----------------
    ("Biology", 11, "The Living World", "Taxonomy (biology)"),
    ("Biology", 11, "Biological Classification", "Biological classification"),
    ("Biology", 11, "Plant Kingdom", "Plant"),
    ("Biology", 11, "Animal Kingdom", "Animal"),
    ("Biology", 11, "Cell: The Unit of Life", "Cell (biology)"),
    ("Biology", 11, "Cell Cycle and Cell Division", "Cell cycle"),
    ("Biology", 11, "Photosynthesis in Higher Plants", "Photosynthesis"),
    ("Biology", 11, "Respiration in Plants", "Cellular respiration"),
    ("Biology", 11, "Digestion and Absorption", "Digestion"),
    ("Biology", 11, "Breathing and Exchange of Gases", "Gas exchange"),
    ("Biology", 11, "Body Fluids and Circulation", "Circulatory system"),
    ("Biology", 11, "Excretory Products and Elimination", "Excretion"),
    ("Biology", 11, "Neural Control and Coordination", "Nervous system"),
    ("Biology", 12, "Sexual Reproduction in Flowering Plants", "Plant reproduction"),
    ("Biology", 12, "Human Reproduction", "Human reproduction"),
    ("Biology", 12, "Reproductive Health", "Reproductive health"),
    ("Biology", 12, "Principles of Inheritance and Variation", "Mendelian inheritance"),
    ("Biology", 12, "Molecular Basis of Inheritance", "Molecular genetics"),
    ("Biology", 12, "Evolution", "Evolution"),
    ("Biology", 12, "Human Health and Disease", "Disease"),
    ("Biology", 12, "Microbes in Human Welfare", "Microorganism"),
    ("Biology", 12, "Biotechnology: Principles and Processes", "Biotechnology"),
    ("Biology", 12, "Organisms and Populations", "Population ecology"),
    ("Biology", 12, "Ecosystem", "Ecosystem"),
    ("Biology", 12, "Biodiversity and Conservation", "Biodiversity"),

    # ---------------- English ----------------
    ("English", 11, "Parts of Speech", "Part of speech"),
    ("English", 11, "Tenses", "Grammatical tense"),
    ("English", 11, "Active and Passive Voice", "Grammatical voice"),
    ("English", 11, "Direct and Indirect Speech", "Indirect speech"),
    ("English", 11, "Figures of Speech", "Figure of speech"),
    ("English", 11, "Letter Writing", "Letter (message)"),
    ("English", 12, "English Grammar Essentials", "English grammar"),
    ("English", 12, "Poetry Appreciation", "Poetry"),
    ("English", 12, "Prose Comprehension", "Prose"),
    ("English", 12, "Essay Writing", "Essay"),
]


def build_concept_jobs():
    jobs = []
    for subject, class_level, topic, wiki_title in TOPICS:
        jobs.append(
            {
                "subject": subject,
                "class_level": class_level,
                "topic": topic,
                "type": "concept",
                "source": "wikipedia",
                "wikipedia_title": wiki_title,
            }
        )
    return jobs


EXAMPLE_PRACTICE_QUESTION_JOB = {
    "_comment": (
        "This is a template, not a live job -- it's disabled so run_scraper.py "
        "skips it. Copy it, point 'url' at a real page of practice questions "
        "you have the right to scrape, fill in the CSS selectors for that "
        "page's markup, and remove _disabled. See generic_scraper.py's "
        "docstring for the full selector reference."
    ),
    "_disabled": True,
    "subject": "Physics",
    "class_level": 11,
    "topic": "Laws of Motion",
    "type": "practice_question",
    "source": "generic_html",
    "url": "https://example.com/class-11-physics/laws-of-motion-practice",
    "source_name": "Example Site",
    "license": "Check the site's terms before reuse",
    "selectors": {
        "item": "div.question",
        "title": ".question-text",
        "options": ".options li",
        "answer": ".answer",
    },
}


def main():
    jobs = build_concept_jobs()
    jobs.append(EXAMPLE_PRACTICE_QUESTION_JOB)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(jobs)} jobs to {out_path}")


if __name__ == "__main__":
    main()
