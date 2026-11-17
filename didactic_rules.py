"""
didactic_rules.py
=================
Authoritative pedagogical framework, curriculum tree, session blueprints,
and compliance validators extracted from the official Algerian Ministry of
National Education / National Curriculum Council (CNP) Didactic Guides:
  - Didactic Guide of English - Key Stage 1 Primary Education (3PS & 4PS, 2023)
  - Didactic Guide of English - Key Stage 3 Primary Education (5PS, 2024)
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. OFFICIAL CURRICULUM FRAMING: VALUES, COMPETENCIES & DOMAINS
# ---------------------------------------------------------------------------

CORE_VALUES: Dict[str, str] = {
    "National Identity": "The learner is proud of being Algerian, Muslim, Arab and Amazigh.",
    "National Conscience": "S/he respects her/his nation's constant fundamental tenets.",
    "Citizenship": "S/he demonstrates respect towards others.",
    "Openness to the World": (
        "S/he exchanges and communicates with friends from English-speaking "
        "countries to widen her/his friendship."
    ),
}

CROSS_CURRICULAR_COMPETENCIES: Dict[str, str] = {
    "Intellectual": (
        "Discover the relationship between the context, paralinguistic features, "
        "and the meaning of words, expressions, and sentences; demonstrate understanding "
        "of decoding/writing strategies."
    ),
    "Methodological": (
        "Make use of context, paralinguistic features, and decoding/writing strategies "
        "to solve communication tasks and build learning habits."
    ),
    "Communicative": (
        "React to verbal and non-verbal messages and select appropriate words, "
        "chunks, and paralinguistic cues to interact with peers."
    ),
    "Personal and Social": (
        "Collaborate respectfully with peers in pair/group tasks, value others' "
        "readings/writings, and participate positively in classroom routines."
    ),
}

DOMAINS_BY_LEVEL: Dict[str, List[str]] = {
    "3PS": [
        "Oral Comprehension",
        "Oral Production",
        "Written Comprehension",
        "Written Production",
    ],
    "4PS": [
        "Oral Comprehension",
        "Oral Production",
        "Written Comprehension",
        "Written Production",
    ],
    "5PS": [
        "Oral Comprehension",
        "Oral Production",
        "Written Comprehension",
        "Written Production",
    ],
}

TARGET_COMPETENCIES: Dict[str, Dict[str, str]] = {
    "3PS": {
        "Oral Comprehension": (
            "Comprehend oral messages and identify the meaning of words in familiar "
            "contexts using paralinguistic features."
        ),
        "Oral Production": (
            "Interact orally in short communicative situations related to the learner's "
            "immediate environment using simple words and formulaic chunks."
        ),
        "Written Comprehension": (
            "Decode symbols, read simple messages of about 30 words, and understand "
            "the meaning of words and structures using graphophonic knowledge and visuals."
        ),
        "Written Production": (
            "Write letters, words, and simple sentences in script/print handwriting "
            "using correct sizing, spacing, alignment, and punctuation."
        ),
    },
    "4PS": {
        "Oral Comprehension": (
            "Comprehend oral messages and identify the meaning of words, expressions, "
            "and sentences in familiar contexts using paralinguistic features."
        ),
        "Oral Production": (
            "Interact orally in communicative situations related to the learner's "
            "immediate environment, daily concerns, and interests using simple words, "
            "expressions, and sentences."
        ),
        "Written Comprehension": (
            "Decode symbols, read simple messages of about 30-40 words, and understand "
            "the meaning of words and sentences using reading basics and decoding strategies."
        ),
        "Written Production": (
            "Produce words using connected/joined (cursive) handwriting to fill in a "
            "topic-related form with specific details from the learner's immediate environment."
        ),
    },
    "5PS": {
        "Oral Comprehension": (
            "Comprehend short oral passages (20-40 words) and identify the overall idea "
            "and specific details using context and visual aids."
        ),
        "Oral Production": (
            "Interact orally in personalized real-life communicative situations using "
            "target chunks, appropriate intonation, and intelligible pronunciation."
        ),
        "Written Comprehension": (
            "Decode and read short simple texts (~20/30/40 words by sequence level) with "
            "meaningful chunking to locate the overall idea and specific details."
        ),
        "Written Production": (
            "Transform notes from a form into simple accurate sentences (~10/15/20 words) "
            "and link them into a short message using proper writing mechanics (writing for reinforcement)."
        ),
    },
}

# ---------------------------------------------------------------------------
# 2. GRADE METADATA & PEDAGOGICAL CONSTRAINTS
# ---------------------------------------------------------------------------

GRADE_META: Dict[str, Dict[str, Any]] = {
    "3PS": {
        "id": "3PS",
        "label": "3PS - Year 3 Primary (Key Stage 1)",
        "short_label": "3PS (Year 3)",
        "key_stage": "Key Stage 1",
        "guide_title": "Didactic Guide of English - Key Stage 1 Primary Education",
        "guide_year": 2023,
        "session_duration_minutes": 60,
        "sessions_per_section": 4,
        "project_title": "My Pictionary",
        "handwriting_style": (
            "Print/script handwriting ONLY by letter formation families (lowercase then "
            "UPPERCASE; sizing, spacing, alignment). No cursive and no free paragraph writing."
        ),
        "exit_profile": (
            "Interact orally, comprehend oral messages and identify the meaning of words, "
            "decode symbols, read simple messages, and write letters, words, and simple sentences."
        ),
    },
    "4PS": {
        "id": "4PS",
        "label": "4PS - Year 4 Primary (Key Stage 1)",
        "short_label": "4PS (Year 4)",
        "key_stage": "Key Stage 1",
        "guide_title": "Didactic Guide of English - Key Stage 1 Primary Education",
        "guide_year": 2023,
        "session_duration_minutes": 60,
        "sessions_per_section": 5,
        "project_title": "Mini Dictionary",
        "handwriting_style": (
            "Connected/joined (cursive) handwriting used to complete topic-related forms "
            "(e.g., ID cards, family trees, health forms) rather than free essays."
        ),
        "exit_profile": (
            "Interact orally, comprehend oral messages and identify the meaning of words, "
            "expressions and simple sentences, decode symbols, read simple messages, and "
            "produce relevant information to fill in a form."
        ),
    },
    "5PS": {
        "id": "5PS",
        "label": "5PS - Year 5 Primary (Key Stage 3)",
        "short_label": "5PS (Year 5)",
        "key_stage": "Key Stage 3",
        "guide_title": "Didactic Guide of English - Key Stage 3 Primary Education",
        "guide_year": 2024,
        "session_duration_minutes": 45,
        "sessions_per_section": 8,
        "project_title": "My Booklet",
        "handwriting_style": (
            "Joined handwriting transforming notes from a form into simple accurate "
            "sentences (~10/15/20 words) linked into a short message (writing for reinforcement)."
        ),
        "exit_profile": (
            "Interact orally, comprehend short oral/written passages, notice language "
            "patterns implicitly, and transfer form notes into short accurate messages."
        ),
    },
}

OBJECTIVE_FORMULA_PREFIX = "By the end of the session, learners will be able to"

OFFICIAL_HEADER_FIELDS: Tuple[str, ...] = (
    "Class profile",
    "Level",
    "Number of learners",
    "Duration",
    "Sequence",
    "Section",
    "Session",
    "Domain(s)",
    "Target competence",
    "Session Objective(s)",
    "Subsidiary objective(s)",
    "Phonics / Language focus",
    "Core values",
    "Cross-curricular competencies",
    "Teaching materials",
    "Anticipated problems",
    "Solutions/Plan B",
)

SELF_REFLECTION_FIELDS: Tuple[str, ...] = (
    "What worked",
    "What hindered",
    "Action plan",
)

# ---------------------------------------------------------------------------
# 3. PEDAGOGICAL RED FLAGS & NON-MONETARY GAMIFICATION CONSTRAINTS
# ---------------------------------------------------------------------------

PEDAGOGICAL_CONSTRAINTS: Dict[str, List[str]] = {
    "COMMON": [
        "Every session must match the official session duration for its level (60 minutes for 3PS and 4PS; 45 minutes for 5PS) across its ordered stages.",
        "Session Objective(s) must follow the formula: 'By the end of the session, learners will be able to ...'",
        "Grammar must ALWAYS be taught implicitly in context (chunks in 3PS/4PS; inductive discovery in 5PS) — NEVER lecture on explicit grammatical rules or metalanguage.",
        "Young concrete-operational learners (ages 7-11) require VAKT multisensory aids (flashcards, realia, gestures, mimes, songs, slates).",
        "Never use learner-facing didactic meta-terms ('skim', 'scan', 'gist', 'prediction') when addressing pupils.",
        "Any classroom gamification or motivation must strictly use non-monetary rewards (stars, explorer badges, team points, stickers, smiley/traffic cards).",
    ],
    "3PS": [
        "Session timing: 60 minutes total across ordered stages.",
        "Print/script handwriting ONLY by formation families (no cursive, no free essay/paragraph writing).",
        "No written text on the board during Session 1 ('I Sing & Have Fun / I Listen & Repeat').",
        "Phonemic awareness in 3PS covers isolating, blending, and segmenting VC/CVC sounds only; NO sight-word memorization.",
        "4 sessions per section: I Sing & Have Fun / I Listen & Repeat -> I Read & Discover -> I Read & Write -> I Play Roles.",
    ],
    "4PS": [
        "Session timing: 60 minutes total across ordered stages.",
        "Session 4 ('I Read & Write') focuses on completing a topic-related form in connected/joined (cursive) handwriting after reviewing Session 2 text — NOT free composition.",
        "Session 3 ('I Read & Enjoy') runs structured, inclusive reading games with rules explained and demonstrated beforehand.",
        "Short texts scale from ~30 words (Seq 1-2) to ~35 words (Seq 3-4) and ~40 words (Seq 5); NO sight-word drills.",
        "5 sessions per section: I Sing & Have Fun / I Listen & Repeat -> I Read & Discover -> I Read & Enjoy -> I Read & Write -> I Play Roles.",
    ],
    "5PS": [
        "Session timing: 45 minutes total across ordered stages.",
        "Writing is 'writing for reinforcement' (transforming form notes into ~10/15/20-word messages), NOT free essay writing ('writing for communication').",
        "Listening requires multiple passes (more than one listening); reading prioritizes meaningful chunking and checking HOW learners found answers.",
        "In 'I Read and Understand', provide 1 overall-idea (skimming) task and 1 detail-finding (scanning) task.",
        "Use fingers for word boundaries and hand movements for intonation during 'I Listen and Discover'.",
        "Store 'I Get Ready' answer sheets in learners' portfolios for 'I Check My Progress'.",
    ],
}

RED_FLAG_RULES: List[Dict[str, str]] = [
    {
        "id": "implicit-grammar",
        "severity": "critical",
        "title": "Explicit Grammar Teaching Prohibited",
        "description": "Never present abstract grammar rules or terminology to learners; use formulaic chunks (KS1) or inductive discovery (KS3).",
        "guide_page": "KS1 pp. 15-16, 50; KS3 pp. 20, 44",
    },
    {
        "id": "no-meta-language",
        "severity": "critical",
        "title": "No Learner-Facing Meta-Language",
        "description": "Never use terms like 'skim', 'scan', 'gist', or 'prediction' in learner-facing instructions or scripts.",
        "guide_page": "KS3 p. 53",
    },
    {
        "id": "handwriting-boundary",
        "severity": "critical",
        "title": "Level-Appropriate Handwriting & Writing Stage",
        "description": "3PS uses print handwriting only; 4PS uses cursive form completion; 5PS uses form-to-sentence reinforcement (10-20 words), not free essays.",
        "guide_page": "KS1 pp. 17, 26, 51, 56-57; KS3 pp. 18, 49, 51",
    },
    {
        "id": "time-allocation",
        "severity": "critical",
        "title": "Level-Specific Session Budget (60 mn 3PS/4PS, 45 mn 5PS)",
        "description": "Stage timings must sum accurately to 60 minutes for Year 3 (3PS) & Year 4 (4PS), and 45 minutes for Year 5 (5PS).",
        "guide_page": "KS1 pp. 19, 53, 74; KS3 pp. 28-29, 70-71",
    },
    {
        "id": "non-monetary-gamification",
        "severity": "critical",
        "title": "Non-Monetary Classroom Gamification Only",
        "description": "Classroom games must reward learners with stars, explorer badges, team points, or stickers — never monetary prizes or financial tokens.",
        "guide_page": "AITADZ Pedagogical Standard / KS1 p. 55 / KS3 p. 40",
    },
    {
        "id": "exit-ticket",
        "severity": "warning",
        "title": "Formative Exit Ticket Reflection",
        "description": "Learning sessions conclude with a quick Exit Ticket ('Ticket to leave') checking what learners understood, enjoyed, or found challenging.",
        "guide_page": "KS1 p. 78; KS3 pp. 32, 34, 37, 39, 48, 50, 52, 87",
    },
]

ALLOWED_GAMIFICATION_REWARDS: Tuple[str, ...] = (
    "Gold Stars",
    "Explorer Badges",
    "Team Points",
    "Classroom Stickers",
    "Smiley / Thumbs-up Cards",
)

FORBIDDEN_MONETARY_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bprize\s+money\b", "gold stars and explorer badges"),
    (r"\bcrypto(?:currency)?\b", "explorer badges"),
    (r"\bdollar(?:s)?\b", "team points"),
    (r"\bdinar(?:s)?\b", "team points"),
    (r"\beuro(?:s)?\b", "team points"),
    (r"\bcoin(?:s)?\b", "gold stars"),
    (r"\bbanknote(?:s)?\b", "stickers"),
    (r"\bcash\b", "team points"),
    (r"\bmoney\b", "team points"),
    (r"\btoken(?:s)?\b", "explorer badges"),
    (r"\bbet(?:s|ting)?\b", "friendly team challenge"),
    (r"\bjackpot(?:s)?\b", "bonus star"),
    (r"\bcurrency\b", "classroom stars"),
]

META_TERM_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bskimming\b", "reading quickly for the main idea"),
    (r"\bskim\b", "read quickly for the main idea"),
    (r"\bscanning\b", "looking carefully for specific details"),
    (r"\bscan\b", "look carefully for specific details"),
    (r"\bgist\b", "overall idea"),
    (r"\bpredictions\b", "initial guesses"),
    (r"\bprediction\b", "initial guess"),
]

# ---------------------------------------------------------------------------
# 4. FULL CURRICULUM TREE (3PS, 4PS, 5PS)
# ---------------------------------------------------------------------------

CURRICULUM_TREE: Dict[str, Dict[str, Any]] = {
    "3PS": {
        "sequences": [
            {
                "id": "3ps-seq-1",
                "number": 1,
                "title": "Family & Friends",
                "guide_pages": "KS1 pp. 18, 33-34",
                "sections": [
                    {
                        "id": "3ps-s1-1",
                        "number": 1,
                        "title": "Section 1: Family",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Introduce family members (family relationship and name).",
                            "Ask and answer questions about name.",
                        ],
                        "key_vocabulary": [
                            "parents", "father/dad", "mother/mum", "brother", "sister",
                            "grandfather", "grandmother", "grandparents",
                        ],
                        "implicit_grammar": [
                            "Present simple: to be (contracted 'm/'s), to have",
                            "Wh-question: Who/What...? Personal pronouns",
                        ],
                        "phonics_target": "Print lowercase Family 1: i, j, l, t, u (letter sounds & formation)",
                        "pronunciation_intonation": ["Simple sentences", "Wh-questions (falling intonation)", "Greetings"],
                        "guide_pages": "KS1 pp. 18, 26, 33",
                    },
                    {
                        "id": "3ps-s1-2",
                        "number": 2,
                        "title": "Section 2: Friends",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Greet people and take leave.",
                            "Introduce oneself and a friend (name, age, language, place of residence).",
                            "Count from 0 to 10.",
                        ],
                        "key_vocabulary": ["friend", "mate", "numbers 0-10", "hello", "hi", "goodbye"],
                        "implicit_grammar": [
                            "Present simple: to be, to have, to live",
                            "Wh-questions: What, How old; Pronouns: I, you, he, she, it; Preposition: in",
                        ],
                        "phonics_target": "/i/ spelt 'i' (six, in, live); Print UPPERCASE: I, J, L, T, U ('I' always capitalized)",
                        "pronunciation_intonation": ["Simple sentences", "Questions (what, how old)"],
                        "guide_pages": "KS1 pp. 18, 26, 34",
                    },
                ],
            },
            {
                "id": "3ps-seq-2",
                "number": 2,
                "title": "School",
                "guide_pages": "KS1 pp. 18, 35-36",
                "sections": [
                    {
                        "id": "3ps-s2-1",
                        "number": 1,
                        "title": "Section 1: School Objects",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name and identify classroom objects and their colours.",
                            "Locate classroom objects and ask/answer about them.",
                        ],
                        "key_vocabulary": [
                            "school", "bag", "book", "chair", "eraser", "pencil", "crayon", "pen", "table", "tablet",
                            "black", "white", "blue", "green", "red", "yellow", "brown",
                        ],
                        "implicit_grammar": [
                            "Demonstrative: this; Articles: a, an",
                            "Wh-questions: Where, What; Prepositions: in, on, under",
                        ],
                        "phonics_target": "Print lowercase Family 2: b, h, k, m",
                        "pronunciation_intonation": ["Simple sentences", "Wh-questions"],
                        "guide_pages": "KS1 pp. 18, 26, 35",
                    },
                    {
                        "id": "3ps-s2-2",
                        "number": 2,
                        "title": "Section 2: School Subjects",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name and identify school subjects and days of the week.",
                            "Ask and answer questions about when school subjects take place.",
                        ],
                        "key_vocabulary": [
                            "Arabic", "English", "maths", "science", "music", "art",
                            "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                        ],
                        "implicit_grammar": ["Wh-question: When...?; Preposition: on"],
                        "phonics_target": "/ʌ/ spelt 'u' (under, number, Sunday); Print UPPERCASE: B, H, K, M (capitalize days)",
                        "pronunciation_intonation": ["Simple sentences", "When-questions"],
                        "guide_pages": "KS1 pp. 18, 26, 36",
                    },
                ],
            },
            {
                "id": "3ps-seq-3",
                "number": 3,
                "title": "Home",
                "guide_pages": "KS1 pp. 18, 37-38",
                "sections": [
                    {
                        "id": "3ps-s3-1",
                        "number": 1,
                        "title": "Section 1: Describing a House",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name and identify rooms in a flat/house.",
                            "Ask and answer questions about rooms in a flat/house.",
                        ],
                        "key_vocabulary": [
                            "home", "house", "flat", "bedroom", "kitchen", "living room",
                            "dining room", "bathroom", "toilets", "numbers",
                        ],
                        "implicit_grammar": [
                            "there is / there are; Yes/No question: Is there a...?",
                            "Demonstrative: this; Articles: a, an",
                        ],
                        "phonics_target": "Print lowercase Family 2: n, p, r",
                        "pronunciation_intonation": ["Simple sentences", "Yes/No questions (rising intonation)"],
                        "guide_pages": "KS1 pp. 18, 26, 37",
                    },
                    {
                        "id": "3ps-s3-2",
                        "number": 2,
                        "title": "Section 2: Locating Rooms in a House",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Locate people and rooms in a flat/house.",
                            "Ask and answer questions about where people/rooms are in a house.",
                        ],
                        "key_vocabulary": ["rooms in a house", "family members", "next to", "opposite", "in"],
                        "implicit_grammar": ["Wh-question: Where...?; Prepositions: next to, opposite, in"],
                        "phonics_target": "/p/ vs /b/ (pen/Ben); Print UPPERCASE: N, P, R",
                        "pronunciation_intonation": ["Simple sentences", "Where-questions"],
                        "guide_pages": "KS1 pp. 18, 26, 38",
                    },
                ],
            },
            {
                "id": "3ps-seq-4",
                "number": 4,
                "title": "Playtime",
                "guide_pages": "KS1 pp. 18, 39-40",
                "sections": [
                    {
                        "id": "3ps-s4-1",
                        "number": 1,
                        "title": "Section 1: Toys",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name and identify common toys.",
                            "Ask and answer questions about toys.",
                        ],
                        "key_vocabulary": ["toys", "ball", "bike", "car", "doll", "kite", "robot", "computer", "train"],
                        "implicit_grammar": ["Have you got...?; What / What's...?"],
                        "phonics_target": "Print lowercase Family 3: c, a, d, e, g",
                        "pronunciation_intonation": ["Simple sentences", "Yes/No & Wh-questions"],
                        "guide_pages": "KS1 pp. 18, 26, 39",
                    },
                    {
                        "id": "3ps-s4-2",
                        "number": 2,
                        "title": "Section 2: Favourite Toy",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Ask and answer questions about one's favourite toy and its colour.",
                        ],
                        "key_vocabulary": ["toys", "favourite", "colours"],
                        "implicit_grammar": ["What's your favourite toy? / My favourite toy is... / Its colour's..."],
                        "phonics_target": "/æ/ spelt 'a' (black, bag); Print UPPERCASE: C, A, D, E, G",
                        "pronunciation_intonation": ["Simple sentences", "Wh-questions"],
                        "guide_pages": "KS1 pp. 18, 26, 40",
                    },
                ],
            },
            {
                "id": "3ps-seq-5",
                "number": 5,
                "title": "Pets",
                "guide_pages": "KS1 pp. 18, 41-42",
                "sections": [
                    {
                        "id": "3ps-s5-1",
                        "number": 1,
                        "title": "Section 1: Pets",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name common pets.",
                            "Ask and answer questions about having a pet and its name.",
                        ],
                        "key_vocabulary": ["pet", "cat", "dog", "canary", "chick", "lamb", "goldfish"],
                        "implicit_grammar": ["Have you got a pet?; What is it? / Its name is..."],
                        "phonics_target": "Print lowercase Family 3: o, q, f, s",
                        "pronunciation_intonation": ["Simple sentences", "Questions"],
                        "guide_pages": "KS1 pp. 18, 26, 41",
                    },
                    {
                        "id": "3ps-s5-2",
                        "number": 2,
                        "title": "Section 2: Pet's Body Parts",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Identify and describe a pet's body parts using simple adjectives.",
                        ],
                        "key_vocabulary": ["hair", "tail", "bill", "feather", "fin", "big", "small", "long", "short"],
                        "implicit_grammar": ["Simple descriptive chunks with to have + adjectives"],
                        "phonics_target": "/ɒ/ spelt 'o' (on, dog); Print UPPERCASE: O, Q, F, S",
                        "pronunciation_intonation": ["Simple sentences", "Descriptions"],
                        "guide_pages": "KS1 pp. 18, 26, 42",
                    },
                ],
            },
            {
                "id": "3ps-seq-6",
                "number": 6,
                "title": "Fancy Birthday",
                "guide_pages": "KS1 pp. 18, 43-44",
                "sections": [
                    {
                        "id": "3ps-s6-1",
                        "number": 1,
                        "title": "Section 1: Party Invitation",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Invite friends to a birthday party.",
                            "Respond to a birthday party invitation.",
                        ],
                        "key_vocabulary": ["birthday", "party", "invitation", "guests", "colours", "numbers", "days"],
                        "implicit_grammar": ["Preposition: at; Wh-question: What...?; Imperative"],
                        "phonics_target": "/e/ spelt 'e' (ten, red); Print lowercase Family 4: v, w, x, y, z",
                        "pronunciation_intonation": ["Simple sentences", "Invitations", "Imperatives"],
                        "guide_pages": "KS1 pp. 18, 26, 43",
                    },
                    {
                        "id": "3ps-s6-2",
                        "number": 2,
                        "title": "Section 2: Party Celebration",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name birthday party items, tableware, and feelings.",
                            "Name face parts for a fancy face.",
                        ],
                        "key_vocabulary": [
                            "eyes", "nose", "ears", "mouth", "lips", "cheeks",
                            "candles", "cake", "juice", "sweets", "spoon", "fork", "knife", "glass",
                            "happy", "glad", "excited",
                        ],
                        "implicit_grammar": ["Articles: a, an; Imperative"],
                        "phonics_target": "/f/ vs /v/ (fan/van); Print UPPERCASE: V, W, X, Y, Z",
                        "pronunciation_intonation": ["Simple sentences", "Exclamations", "Imperatives"],
                        "guide_pages": "KS1 pp. 18, 26, 44",
                    },
                ],
            },
        ],
    },
    "4PS": {
        "sequences": [
            {
                "id": "4ps-seq-1",
                "number": 1,
                "title": "Family & Friends",
                "guide_pages": "KS1 pp. 52, 63-64",
                "sections": [
                    {
                        "id": "4ps-s1-1",
                        "number": 1,
                        "title": "Section 1: Family",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Introduce extended family members (relationship, name, age, occupation, residence).",
                            "Ask and answer questions about family members.",
                        ],
                        "key_vocabulary": [
                            "numbers 11-30", "aunts", "uncles", "cousins", "nephews", "nieces",
                            "sons", "daughters", "jobs (-er, -or, -ist)",
                        ],
                        "implicit_grammar": [
                            "Present simple: to be, to live, to have; Possessive adjectives; there is/are",
                            "Questions: who, how old, what; Do/does? Is/are?",
                        ],
                        "phonics_target": "/i/ vs /i:/ (six / green)",
                        "pronunciation_intonation": ["Simple sentences", "Wh- & Yes/No questions"],
                        "guide_pages": "KS1 pp. 52, 63",
                    },
                    {
                        "id": "4ps-s1-2",
                        "number": 2,
                        "title": "Section 2: Friends",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Introduce friends/e-pals (name, age, nationality, residence, language).",
                            "Name countries and nationalities; count from 01 to 30.",
                        ],
                        "key_vocabulary": [
                            "numbers 01-30", "languages", "countries", "nationalities (-sh, -ch, -an, -ian, -ese)",
                        ],
                        "implicit_grammar": [
                            "Present simple: to be, to live, to have, to speak",
                            "Prepositions: in, from; Question: Where... from?",
                        ],
                        "phonics_target": "/ʃ/ vs /ʧ/ (English / French)",
                        "pronunciation_intonation": ["Simple sentences", "Where-questions"],
                        "guide_pages": "KS1 pp. 52, 64",
                    },
                ],
            },
            {
                "id": "4ps-seq-2",
                "number": 2,
                "title": "School",
                "guide_pages": "KS1 pp. 52, 65-66",
                "sections": [
                    {
                        "id": "4ps-s2-1",
                        "number": 1,
                        "title": "Section 1: Facilities",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name school facilities and outdoor spaces.",
                            "Ask and answer questions about school facilities using simple adjectives.",
                        ],
                        "key_vocabulary": [
                            "classrooms", "library", "canteen", "schoolyard", "staffroom",
                            "toilets", "trees", "grass", "flowers", "water taps", "big/clean/nice",
                        ],
                        "implicit_grammar": ["there is / there are; Preposition: in"],
                        "phonics_target": "/ʊ/ vs /u:/ (book / school)",
                        "pronunciation_intonation": ["Simple sentences", "Yes/No questions"],
                        "guide_pages": "KS1 pp. 52, 65",
                    },
                    {
                        "id": "4ps-s2-2",
                        "number": 2,
                        "title": "Section 2: Mapping",
                        "reading_word_target": 30,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Locate school facilities and ask/answer questions about school facility locations.",
                        ],
                        "key_vocabulary": [
                            "classrooms", "library", "canteen", "schoolyard", "staffroom",
                            "on the left", "on the right", "behind", "in front of", "next to", "opposite",
                        ],
                        "implicit_grammar": [
                            "Prepositions of location: in, next to, opposite, on the left/right, behind, in front of",
                            "Wh-question: Where...?",
                        ],
                        "phonics_target": "/ð/ (the, this, brother)",
                        "pronunciation_intonation": ["Simple sentences", "Where-questions"],
                        "guide_pages": "KS1 pp. 52, 66",
                    },
                ],
            },
            {
                "id": "4ps-seq-3",
                "number": 3,
                "title": "Fun Time & Games",
                "guide_pages": "KS1 pp. 52, 67-68",
                "sections": [
                    {
                        "id": "4ps-s3-1",
                        "number": 1,
                        "title": "Section 1: Fun Time",
                        "reading_word_target": 35,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name indoor/outdoor activities, sports, and seasons.",
                            "Ask and answer questions about favourite fun-time activities.",
                        ],
                        "key_vocabulary": [
                            "indoor/outdoor activities", "individual/team sport",
                            "seasons", "weekend", "happy", "excited",
                        ],
                        "implicit_grammar": ["love, prefer, like; Prepositions: on, in; Yes/No question: Do...?"],
                        "phonics_target": "/ɔ:/ (ball, sport, draw)",
                        "pronunciation_intonation": ["Simple sentences", "Do-questions"],
                        "guide_pages": "KS1 pp. 52, 67",
                    },
                    {
                        "id": "4ps-s3-2",
                        "number": 2,
                        "title": "Section 2: Games",
                        "reading_word_target": 35,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name common games (individual, team, physical, mental, digital).",
                            "Ask and answer questions about favourite games.",
                        ],
                        "key_vocabulary": [
                            "board games", "card games", "cord skipping", "hide and seek", "water balloon fight",
                        ],
                        "implicit_grammar": ["Wh-question: What...?"],
                        "phonics_target": "/ɑ:/ (card, park, start)",
                        "pronunciation_intonation": ["Simple sentences", "What-questions"],
                        "guide_pages": "KS1 pp. 52, 68",
                    },
                ],
            },
            {
                "id": "4ps-seq-4",
                "number": 4,
                "title": "Food & Health",
                "guide_pages": "KS1 pp. 52, 69-70",
                "sections": [
                    {
                        "id": "4ps-s4-1",
                        "number": 1,
                        "title": "Section 1: Healthy Food",
                        "reading_word_target": 35,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name healthy food categories, fruits, vegetables, and drinks.",
                            "Talk about eating/drinking healthy food.",
                        ],
                        "key_vocabulary": [
                            "bread", "cereals", "vegetables", "fruit", "meat", "drinks", "dairy", "fish",
                            "tomato", "potato", "orange", "banana", "apple", "chicken", "milk", "water", "fresh juice",
                        ],
                        "implicit_grammar": ["Plural nouns; Present continuous"],
                        "phonics_target": "/ə/ vs /ɜ:/ (banana / burger)",
                        "pronunciation_intonation": ["Simple sentences", "Questions"],
                        "guide_pages": "KS1 pp. 52, 69",
                    },
                    {
                        "id": "4ps-s4-2",
                        "number": 2,
                        "title": "Section 2: Health",
                        "reading_word_target": 35,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name body parts and common illnesses.",
                            "Give simple health advice using Do / Do not.",
                        ],
                        "key_vocabulary": [
                            "head", "shoulders", "knees", "toes", "legs", "arms",
                            "headache", "toothache", "flu", "stomachache",
                        ],
                        "implicit_grammar": ["Imperative: Do / do not..."],
                        "phonics_target": "/θ/ (health, toothache, mouth)",
                        "pronunciation_intonation": ["Simple sentences", "Imperatives (advice)"],
                        "guide_pages": "KS1 pp. 52, 70",
                    },
                ],
            },
            {
                "id": "4ps-seq-5",
                "number": 5,
                "title": "Animals",
                "guide_pages": "KS1 pp. 52, 71-72",
                "sections": [
                    {
                        "id": "4ps-s5-1",
                        "number": 1,
                        "title": "Section 1: Farm Animals",
                        "reading_word_target": 40,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name farm animals, their body parts, and their food.",
                            "Ask and answer questions about what farm animals eat.",
                        ],
                        "key_vocabulary": [
                            "cow", "sheep", "goat", "chicken", "chick", "horse", "duck", "donkey", "mouse",
                            "tail", "beak", "hair", "feather", "horns", "grass", "seeds", "grains", "insects",
                        ],
                        "implicit_grammar": ["Yes/No question: Do they eat...?"],
                        "phonics_target": "Phonics review (short vs long vowels & target consonants)",
                        "pronunciation_intonation": ["Simple sentences", "Yes/No questions"],
                        "guide_pages": "KS1 pp. 52, 71",
                    },
                    {
                        "id": "4ps-s5-2",
                        "number": 2,
                        "title": "Section 2: Zoo Animals",
                        "reading_word_target": 40,
                        "writing_word_target": 0,
                        "communicative_objectives": [
                            "Name zoo animals, their habitats, food, and characteristics.",
                            "Describe zoo animals using simple adjectives.",
                        ],
                        "key_vocabulary": [
                            "lion", "zebra", "elephant", "panda", "giraffe", "tiger", "snake", "deer",
                            "cage", "habitat", "meat", "grass", "fast", "tall", "big",
                        ],
                        "implicit_grammar": ["Simple descriptive sentences & questions"],
                        "phonics_target": "Phonics review across Year 4 target sounds",
                        "pronunciation_intonation": ["Simple sentences", "Descriptions"],
                        "guide_pages": "KS1 pp. 52, 72",
                    },
                ],
            },
        ],
    },
    "5PS": {
        "sequences": [
            {
                "id": "5ps-seq-1",
                "number": 1,
                "title": "Jobs, Occupations and Hobbies",
                "guide_pages": "KS3 pp. 27, 58-61, 70",
                "sections": [
                    {
                        "id": "5ps-s1-1",
                        "number": 1,
                        "title": "Section 1: Jobs and Occupations",
                        "reading_word_target": 20,
                        "writing_word_target": 10,
                        "communicative_objectives": [
                            "Name/identify common jobs and occupations.",
                            "Ask and answer questions about family members' and friends' jobs.",
                            "Name/identify common places of work.",
                        ],
                        "key_vocabulary": [
                            "farmer", "teacher", "doctor", "dentist", "musician", "gendarme", "manager", "surgeon",
                            "school", "hospital", "farm", "office", "post office", "private company",
                        ],
                        "implicit_grammar": [
                            "Present simple: to do, to be, to work (full & contracted forms)",
                            "Wh-questions: What's her/his/your father's job? Yes/No: Is s/he a doctor?",
                            "Articles: a, an; Prepositions: in, at; word order & SV agreement",
                        ],
                        "phonics_target": "/ʒ/ vs /dʒ/ (pleasure/television vs just/age/judge)",
                        "pronunciation_intonation": ["Simple sentences", "Wh-questions"],
                        "guide_pages": "KS3 pp. 27, 58-59, 80",
                    },
                    {
                        "id": "5ps-s1-2",
                        "number": 2,
                        "title": "Section 2: Hobbies",
                        "reading_word_target": 20,
                        "writing_word_target": 10,
                        "communicative_objectives": [
                            "Identify/name different hobbies and family members' favourite hobbies.",
                            "Ask and answer questions about favourite hobbies.",
                        ],
                        "key_vocabulary": [
                            "playing football/basketball/tennis", "riding a bike", "painting", "swimming",
                            "taking pictures", "playing chess", "creating collages", "days of the week", "weekend",
                        ],
                        "implicit_grammar": [
                            "Present simple: to like, to love, to enjoy, to prefer + stem + -ing",
                            "Wh-question: What's your favourite hobby? Yes/No: Do you like...?",
                            "Prepositions: in, on, at (in the park, at night, on Saturday)",
                        ],
                        "phonics_target": "/ŋ/ (playing, riding, swimming, sing, finger)",
                        "pronunciation_intonation": ["Simple sentences", "Wh- & Yes/No questions", "Exclamations: Fantastic!"],
                        "guide_pages": "KS3 pp. 27, 60-61, 81",
                    },
                ],
            },
            {
                "id": "5ps-seq-2",
                "number": 2,
                "title": "Hometown / City / Village: Amenities, Directions & Signs",
                "guide_pages": "KS3 pp. 27, 62-65, 70",
                "sections": [
                    {
                        "id": "5ps-s2-1",
                        "number": 1,
                        "title": "Section 1: Hometown / City / Village Amenities",
                        "reading_word_target": 30,
                        "writing_word_target": 15,
                        "communicative_objectives": [
                            "Name/identify different amenities in city/hometown/village.",
                            "Ask and answer questions about amenities and their location.",
                        ],
                        "key_vocabulary": [
                            "school", "hospital", "shop", "restaurant", "street", "park", "the butcher's",
                            "the baker's", "the grocer's", "post office", "petrol station", "mall", "florist's", "cafeteria", "bank",
                        ],
                        "implicit_grammar": [
                            "Present simple: to be, to have, to find; Is there/Are there...?; Where is...?",
                            "Possessive case ('s), Articles (a, an, the), Prepositions (in, in front of, between, next to, opposite)",
                        ],
                        "phonics_target": "/j/ (yes, young) vs /w/ (when, what, water)",
                        "pronunciation_intonation": ["Simple sentences", "Yes/No questions", "Exclamations: What a beautiful park!"],
                        "guide_pages": "KS3 pp. 27, 62-63, 82",
                    },
                    {
                        "id": "5ps-s2-2",
                        "number": 2,
                        "title": "Section 2: Directions and Signs",
                        "reading_word_target": 30,
                        "writing_word_target": 15,
                        "communicative_objectives": [
                            "Ask for and show the way to different amenities in city/hometown/village.",
                        ],
                        "key_vocabulary": [
                            "roads", "streets", "traffic lights", "sign(s)", "bridge", "corner", "subway",
                            "pedestrian crossing", "sidewalk", "to the right/left", "up/down the road",
                        ],
                        "implicit_grammar": [
                            "Imperative: go straight ahead, turn right/left, take the first/second turning, cross",
                            "Modal 'can' for polite requests: Excuse me, can you show me the way to...?",
                            "Ordinals (first, second...); Possessive 's",
                        ],
                        "phonics_target": "Revision of target consonant sounds (/j/, /w/, /ʒ/, /dʒ/, /ŋ/)",
                        "pronunciation_intonation": ["Instructions", "Polite requests"],
                        "guide_pages": "KS3 pp. 27, 64-65, 83",
                    },
                ],
            },
            {
                "id": "5ps-seq-3",
                "number": 3,
                "title": "Holidays and Travelling",
                "guide_pages": "KS3 pp. 27, 66-69, 71",
                "sections": [
                    {
                        "id": "5ps-s3-1",
                        "number": 1,
                        "title": "Section 1: Holidays",
                        "reading_word_target": 40,
                        "writing_word_target": 20,
                        "communicative_objectives": [
                            "Name common places/destinations for holidays.",
                            "Ask and answer questions about holiday destinations.",
                        ],
                        "key_vocabulary": [
                            "beach", "mountain", "seaside", "camping", "hotel", "forest", "park", "sandcastles",
                            "winter", "spring", "summer", "autumn",
                        ],
                        "implicit_grammar": [
                            "Present continuous: am/is/are + stem + -ing (full & contracted forms)",
                            "Wh-question: Where are you going for holidays? Yes/No: Are you going...?",
                        ],
                        "phonics_target": "Revision of target sounds",
                        "pronunciation_intonation": ["Simple sentences", "Questions", "Exclamations: Cool! Great!"],
                        "guide_pages": "KS3 pp. 27, 66-67, 84",
                    },
                    {
                        "id": "5ps-s3-2",
                        "number": 2,
                        "title": "Section 2: Travelling",
                        "reading_word_target": 40,
                        "writing_word_target": 20,
                        "communicative_objectives": [
                            "Name/identify different means of transportation.",
                            "Ask and answer questions about favourite ways of travelling.",
                        ],
                        "key_vocabulary": [
                            "car", "plane", "bike", "boat", "train", "metro", "bus",
                            "market", "souvenirs", "weather", "countryside",
                        ],
                        "implicit_grammar": [
                            "Present simple: to like/love/enjoy/prefer + travelling",
                            "Wh-question: How do you like travelling? Prepositions: by, on",
                        ],
                        "phonics_target": "Revision of target sounds",
                        "pronunciation_intonation": ["Simple sentences", "Questions", "Exclamations: Oh! Really!"],
                        "guide_pages": "KS3 pp. 27, 68-69, 85",
                    },
                ],
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# 5. OFFICIAL SESSION BLUEPRINTS (60 MN FOR 3PS/4PS; 45 MN FOR 5PS)
# ---------------------------------------------------------------------------

SESSION_BLUEPRINTS: Dict[str, List[Dict[str, Any]]] = {
    "3PS": [
        {
            "id": "3ps-listen-repeat",
            "title": "Session 1: I Sing & Have Fun / I Listen & Repeat",
            "short_title": "I Sing & Listen/Repeat",
            "occurrence": "Session 1 of every Year 3 Section (60 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 20-23, 28-30, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: I Sing and Have Fun (Warmer)",
                    "procedure": (
                        "Display topic visuals/flashcards. Play or sing the section song twice so learners "
                        "notice rhythm and pitch, then sing together using gestures while the teacher circulates."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral Comprehension | Song audio, topic flashcards",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: I Listen and Repeat — Listening & Visuals (Install Resources)",
                    "procedure": (
                        "Introduce context strictly via flashcards, realia, and mimes (NO written text on board). "
                        "Model target words/chunks clearly and ask short oral comprehension questions."
                    ),
                    "interaction": "T-Ls / Ls-T",
                    "competency_materials": "Oral Comprehension | Flashcards, realia, puppets (NO written text)",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Drilling & Phonemic Awareness (Install Resources)",
                    "procedure": (
                        "Lead choral then individual repetition of target chunks. Run a non-monetary classroom game "
                        "(e.g., Echo Star Challenge) to isolate, blend, and segment VC and CVC sounds orally."
                    ),
                    "interaction": "Whole class / Individual",
                    "competency_materials": "Oral Production | Puppets, flashcards, Star Tracker",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Quick 'Ticket to leave': each learner points to a visual or repeats one target chunk "
                        "before earning a class sticker or team star."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket prompts, stickers",
                },
            ],
        },
        {
            "id": "3ps-read-discover",
            "title": "Session 2: I Read & Discover",
            "short_title": "I Read & Discover",
            "occurrence": "Session 2 of every Year 3 Section (60 mn)",
            "domains": ["Written Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 23-25, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: Warm-up / Phonemic Awareness (Warmer)",
                    "procedure": (
                        "Review target sounds through a rhythmic clapping chant or quick song warm-up; "
                        "diagnose recall from Session 1."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral / Phonemic Awareness | Sound flashcards, rhythm claps",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: Decoding — Segmentation, Blending & Chunking (Install Resources)",
                    "procedure": (
                        "Model left-to-right finger tracking under target words, focusing strictly on letter sounds "
                        "(not letter names) and vowels; guide learners to segment and blend (NO sight words)."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Written Comprehension | Letter-sound cards, pointer",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Present Meaning & 3-Sound Word Cards (Install Resources)",
                    "procedure": (
                        "Connect decoded words to meaning using pictures and miming. Pairs practice decoding "
                        "3-sound word cards to earn team points and explorer badges."
                    ),
                    "interaction": "T-Ls / Pair",
                    "competency_materials": "Written Comprehension | 3-sound word cards, picture cards",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: learners decode one 3-sound word card aloud and match it to its picture."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket cards, gold stars",
                },
            ],
        },
        {
            "id": "3ps-read-write",
            "title": "Session 3: I Read & Write",
            "short_title": "I Read & Write",
            "occurrence": "Session 3 of every Year 3 Section (60 mn)",
            "domains": ["Written Comprehension", "Written Production"],
            "guide_pages": "KS1 pp. 17, 25-27, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: Warm-up / Rhythmic Pattern & Stroke Exercises (Warmer)",
                    "procedure": (
                        "Activate fine motor skills with air-tracing and left-to-right rhythmic stroke patterns "
                        "on slates; review target sound-letter matches."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Written Production | Slates, markers, stroke poster",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: Print Letter & Word Formation Modelling (Install Resources)",
                    "procedure": (
                        "Model PRINT/script handwriting ONLY by formation families (lowercase then UPPERCASE) on "
                        "lined board grids, highlighting sizing, spacing, and alignment (no cursive)."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Lined whiteboard, print letter family chart",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Guided & Independent Print Writing (Install Resources)",
                    "procedure": (
                        "Learners trace, copy, and write target print letters, words, and simple short sentences "
                        "applying capitalization and English punctuation (?, ., ,) — no free composition."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Written Production | Slates, copybooks, print guide strips",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: hold up slates showing one neatly aligned print word; peers show "
                        "smiley/thumbs-up feedback and earn team points."
                    ),
                    "interaction": "Individual / Whole class",
                    "competency_materials": "Formative Assessment | Slates, smiley cards, stickers",
                },
            ],
        },
        {
            "id": "3ps-play-roles",
            "title": "Session 4: I Play Roles",
            "short_title": "I Play Roles",
            "occurrence": "Session 4 of every Year 3 Section (60 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 15-16, 27, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Energize learners with a quick section song/mime game activating key words and "
                        "communicative chunks from the section."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral Production | Flashcards, puppets",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: Dialogue Modelling & Pair/Group Preparation (Install Resources)",
                    "procedure": (
                        "Model a short authentic dialogue from the section using puppets/gestures. Organize pairs "
                        "or small groups to rehearse roles naturally without grammar lectures."
                    ),
                    "interaction": "T-Ls / Pair / Small Group",
                    "competency_materials": "Oral Production | Dialogue cue visuals, props, puppets",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Role-Play Performance & Supportive Feedback (Assessment)",
                    "procedure": (
                        "Pairs/groups act out the dialogue in front of the class; peers applaud and award "
                        "Explorer Badges and Team Stars for clear speaking and polite turn-taking."
                    ),
                    "interaction": "Pair / Whole class",
                    "competency_materials": "Oral Production | Props, classroom Star Chart",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: learners point to an emoji reflecting how confident they feel and "
                        "exchange a farewell chunk with the teacher."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Emoji Exit Ticket chart",
                },
            ],
        },
    ],
    "4PS": [
        {
            "id": "4ps-listen-repeat",
            "title": "Session 1: I Sing & Have Fun / I Listen & Repeat",
            "short_title": "I Sing & Listen/Repeat",
            "occurrence": "Session 1 of every Year 4 Section (60 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 50, 54, 20-23, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: I Sing and Have Fun (Warmer)",
                    "procedure": (
                        "Introduce the topic song with visuals; learners listen to rhythm and pitch, then sing "
                        "together with TPR actions while teacher circulates."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral Comprehension | Song audio, flashcards",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: I Listen and Repeat — Listening & Visuals (Install Resources)",
                    "procedure": (
                        "Present new expressions/chunks using pictures, realia, and mimes without written text. "
                        "Ask short oral comprehension questions to check understanding."
                    ),
                    "interaction": "T-Ls / Ls-T",
                    "competency_materials": "Oral Comprehension | Visual flashcards, realia (NO written text)",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Drilling & Phonemic Awareness (Install Resources)",
                    "procedure": (
                        "Conduct choral then individual drilling of formulaic chunks, plus sound isolation/blending "
                        "through a lively team points mini-challenge."
                    ),
                    "interaction": "Whole class / Individual",
                    "competency_materials": "Oral Production | Flashcards, Team Points board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: learners answer one short oral prompt from a flashcard to collect a "
                        "gold star sticker."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket prompt, stickers",
                },
            ],
        },
        {
            "id": "4ps-read-discover",
            "title": "Session 2: I Read & Discover",
            "short_title": "I Read & Discover",
            "occurrence": "Session 2 of every Year 4 Section (60 mn)",
            "domains": ["Written Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 51, 54, 23-25, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: Warm-up / Phonemic Awareness (Warmer)",
                    "procedure": (
                        "Activate target Year 4 vowels/consonants with rhythm clapping and quick oral diagnostic check."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Written Comprehension | Phonics sound cards",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: Decoding & Short Text Discovery (Install Resources)",
                    "procedure": (
                        "Guide learners to decode a short level-appropriate text (~30-40 words) via segmentation, "
                        "blending, and chunking (NO sight-word drills)."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Written Comprehension | Short reading poster (~30-40 words)",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Meaning Check & Word/Sentence Cards (Install Resources)",
                    "procedure": (
                        "Confirm meaning via visuals/miming; pairs match sentence strips to pictures and earn "
                        "Explorer Badges for accurate decoding."
                    ),
                    "interaction": "T-Ls / Pair",
                    "competency_materials": "Written Comprehension | Sentence strips, visual cards",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: decode one target phrase from the reading text and show emoji self-check."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Word cards, emoji cards",
                },
            ],
        },
        {
            "id": "4ps-read-enjoy",
            "title": "Session 3: I Read & Enjoy",
            "short_title": "I Read & Enjoy",
            "occurrence": "Session 3 of every Year 4 Section (60 mn)",
            "domains": ["Written Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 55-56, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 10,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Quick flashcard flash-and-say energizer reviewing section vocabulary and phonics."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral / Written Comprehension | Topic flashcards",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 2: Game Setup & Rule Demonstration (Install Resources)",
                    "procedure": (
                        "Introduce the structured reading game (e.g., Board Race, Word Jumble Race, Pictionary). "
                        "Explain rules clearly and demonstrate one full round with volunteers."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Comprehension | Game cards, board markers",
                },
                {
                    "minutes": 30,
                    "stage": "Stage 3: Structured Inclusive Reading Games & Review (Install Resources / Practice)",
                    "procedure": (
                        "Run friendly team rounds engaging EVERY learner in reading, spelling, and pronunciation. "
                        "Award non-monetary Team Points, Gold Stars, and Explorer Badges."
                    ),
                    "interaction": "Group / Whole class",
                    "competency_materials": "Written Comprehension | Word cards, team star board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: each learner reads one word/phrase from the game and places a star "
                        "on their favourite activity."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket star board",
                },
            ],
        },
        {
            "id": "4ps-read-write",
            "title": "Session 4: I Read & Write",
            "short_title": "I Read & Write",
            "occurrence": "Session 4 of every Year 4 Section (60 mn)",
            "domains": ["Written Comprehension", "Written Production"],
            "guide_pages": "KS1 pp. 51, 56-57, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 10,
                    "stage": "Stage 1: Warm-up / Cursive Handwriting Habit Modelling (Warmer)",
                    "procedure": (
                        "Warm up writing posture and model connected/joined (cursive) letter joins, sizing, "
                        "spacing, and tall/short/descender alignment on board lines."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Lined whiteboard, cursive chart",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 2: Session 2 Text Review (Install Resources)",
                    "procedure": (
                        "Refer back to the Session 2 ('I Read & Discover') short text; learners read it aloud "
                        "and identify key words needed for writing."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Written Comprehension | Session 2 text poster",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 3: Topic-Related Form Introduction (Install Resources)",
                    "procedure": (
                        "Display a topic-related form (e.g., ID card, family tree, facility card, health form) "
                        "and check learners' understanding of each form field orally."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Model form poster, sample cards",
                },
                {
                    "minutes": 25,
                    "stage": "Stage 4: Form Completion in Connected/Joined (Cursive) Handwriting (Assessment)",
                    "procedure": (
                        "Learners select appropriate words/expressions from the section to complete the form "
                        "using connected/joined (cursive) handwriting (NOT free essay writing) while teacher monitors."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Written Production | Printed/slate forms, copybooks",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 5: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: learners present one neatly joined word from their completed form "
                        "and earn a Handwriting Star."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket, stickers",
                },
            ],
        },
        {
            "id": "4ps-play-roles",
            "title": "Session 5: I Play Roles",
            "short_title": "I Play Roles",
            "occurrence": "Session 5 of every Year 4 Section (60 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS1 pp. 50, 57, 27, 78",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 15,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Lively oral warm-up song or quick charades activating section chunks and expressions."
                    ),
                    "interaction": "T-Ls / Whole class",
                    "competency_materials": "Oral Production | Flashcards, props",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 2: Dialogue Modelling & Preparation (Install Resources)",
                    "procedure": (
                        "Model a short communicative dialogue from the section's listened/read material; guide "
                        "pairs/small groups in rehearsing expressions and gestures."
                    ),
                    "interaction": "T-Ls / Pair / Small Group",
                    "competency_materials": "Oral Production | Role-play cue cards, props",
                },
                {
                    "minutes": 20,
                    "stage": "Stage 3: Role-Play Performance & Supportive Feedback (Assessment)",
                    "procedure": (
                        "Pairs/groups act out the dialogue authentically; peers express appreciation with "
                        "thumbs-up cards and award Explorer Badges and Team Points."
                    ),
                    "interaction": "Pair / Whole class",
                    "competency_materials": "Oral Production | Props, badge board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 4: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Ticket to leave: learners share one expression they enjoyed using and pick an emoji card."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Emoji Exit Ticket cards",
                },
            ],
        },
    ],
    "5PS": [
        {
            "id": "5ps-get-ready",
            "title": "I Get Ready",
            "short_title": "I Get Ready",
            "occurrence": "Beginning of Sequence (Section 1, Session 1 — 45 mn)",
            "domains": ["Oral Comprehension", "Written Comprehension", "Written Production"],
            "guide_pages": "KS3 pp. 29-30, 52, 70-79",
            "requires_exit_ticket": False,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Objective Sharing & Motivation (Warmer)",
                    "procedure": (
                        "Share the sequence discovery goal in a welcoming tone and activate learners' prior "
                        "representations using sequence visuals."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "All Domains | Sequence visuals, portfolio folders",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 2: Listening Initial Task (Diagnostic)",
                    "procedure": (
                        "Introduce listening context, read the short initial listening script aloud, and guide "
                        "learners through picture-matching / overall-idea tasks on portfolio sheets."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Oral Comprehension | Listening script, worksheets",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 3: Reading Initial Tasks (Diagnostic)",
                    "procedure": (
                        "Learners read the short text silently (familiarization) then aloud (decoding check), "
                        "then complete one overall-idea task and one detail-finding task."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Written Comprehension | Initial reading text, portfolio sheets",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 4: Form-to-Paragraph Task & Portfolio Storage (Diagnostic)",
                    "procedure": (
                        "Learners read a form/chart and write a short corresponding message, then store answer "
                        "sheets safely in personal portfolios for 'I Check My Progress'."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Written Production | Form prompt, personal portfolios",
                },
            ],
        },
        {
            "id": "5ps-listen-interact",
            "title": "I Listen and Interact",
            "short_title": "I Listen & Interact",
            "occurrence": "Section 1 Session 2 / Section 2 Session 1 (45 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS3 pp. 31-33, 53, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Run a lively phonemic awareness game (blending, rhyming, adding/deleting sounds) "
                        "and display visual aids to activate key vocabulary."
                    ),
                    "interaction": "T-Ls / Ls-Ls",
                    "competency_materials": "Oral Comprehension | Flashcards, realia",
                },
                {
                    "minutes": 7,
                    "stage": "Stage 2: Anticipation / Prediction (Pre-listening)",
                    "procedure": (
                        "Display topic pictures and ask simple descriptive questions; learners make an initial "
                        "guess individually then share via Think-Pair-Share (TPS)."
                    ),
                    "interaction": "T-Ls / Pair (TPS)",
                    "competency_materials": "Oral Production | Topic pictures, TPS cue",
                },
                {
                    "minutes": 8,
                    "stage": "Stage 3: Checking Initial Guesses (While-listening)",
                    "procedure": (
                        "Read/play the listening script clearly so learners check their initial guesses via "
                        "self-assessment and whole-class confirmation."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Oral Comprehension | Audio / teacher script",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 4: Listening for Overall Idea (While-listening)",
                    "procedure": (
                        "Set ONE unambiguous task (Yes/No, True/False, or 3-option MCQ). Allow multiple listenings "
                        "(listening once is never enough), use mimes/gestures, and encourage self-correction."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Oral Comprehension | Audio/script, board task",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 5: Follow-up / Real-life Assessment (Post-listening)",
                    "procedure": (
                        "Personalize content to learners' real lives through pair role-plays or info-gap "
                        "exchanges; award Team Points and Explorer Badges."
                    ),
                    "interaction": "Pair / Group",
                    "competency_materials": "Oral Production | Role-play prompts, star tracker",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 6: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket ('Ticket to leave'): learners share one thing they learned, enjoyed, "
                        "and found challenging."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket slips/cards",
                },
            ],
        },
        {
            "id": "5ps-listen-discover",
            "title": "I Listen and Discover",
            "short_title": "I Listen & Discover",
            "occurrence": "Section 1 Session 3 / Section 2 Session 2 (45 mn)",
            "domains": ["Oral Comprehension", "Oral Production"],
            "guide_pages": "KS3 pp. 33-34, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Lively phonemic awareness game sounding topical words (segmenting, blending, syllable division)."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Oral Production | Word/sound cards",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 2: Presentation / Discovery (Install Resources)",
                    "procedure": (
                        "Review the listening passage from 'I Listen and Interact'; ask oral leading questions "
                        "so learners notice target word order and patterns IMPLICITLY (no grammar terminology)."
                    ),
                    "interaction": "T-Ls / Ls-T",
                    "competency_materials": "Oral Comprehension | Listening script, flashcards",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 3: Mechanical Practice — Controlled & Guided (Install Resources)",
                    "procedure": (
                        "Phase 1 Controlled: varied drilling using fingers for word boundaries and hand gestures "
                        "for intonation with immediate accuracy feedback. Phase 2 Guided: substitution drills in pairs."
                    ),
                    "interaction": "T-Ls / Pair",
                    "competency_materials": "Oral Production | Visual prompts, puppets, finger/hand cues",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 4: Communicative Practice / Assessment (Assessment)",
                    "procedure": (
                        "Personalized real-life pair role-plays using the target structure creatively; award "
                        "Gold Stars and Team Points for accurate interaction."
                    ),
                    "interaction": "Pair / Group",
                    "competency_materials": "Oral Production | Cue cards, star board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 5: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners demonstrate one target oral question/answer and reflect on learning."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket cards",
                },
            ],
        },
        {
            "id": "5ps-read-understand",
            "title": "I Read and Understand",
            "short_title": "I Read & Understand",
            "occurrence": "Section 1 Session 4 / Section 2 Session 3 (45 mn)",
            "domains": ["Written Comprehension", "Oral Production"],
            "guide_pages": "KS3 pp. 35-37, 53, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Quick vocabulary/phonics game activating prior knowledge and target consonant/vowel sounds."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Comprehension | Phonics cards, flashcards",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 2: Anticipation / Picture Guessing (Pre-reading)",
                    "procedure": (
                        "Show topic visuals; encourage learners to describe what they see and share initial "
                        "guesses about the text topic with peers."
                    ),
                    "interaction": "T-Ls / Ls-Ls",
                    "competency_materials": "Oral Production | Topic illustrations",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 3: Checking Initial Guesses (While-reading)",
                    "procedure": (
                        "Learners read the short text silently (~20-40 words) to verify their initial guesses, "
                        "followed by whole-class cross-checking."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Written Comprehension | Short reading text (~20-40w)",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 4: Reading — Decoding/Chunking & Comprehension (While-reading)",
                    "procedure": (
                        "Phase 1 Decoding: teacher models aloud while learners follow silently, then individual "
                        "aloud reading in meaningful chunks (never rushing speed). Phase 2 Comprehension: ONE "
                        "overall-idea task + ONE detail-finding task (form/chart), checking HOW learners found answers."
                    ),
                    "interaction": "T-Ls / Individual / Pair",
                    "competency_materials": "Written Comprehension | Text sheet, comprehension grid",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 5: Follow-up / Real-life Assessment (Post-reading)",
                    "procedure": (
                        "Pair/group oral exchange connecting the text topic to learners' own lives; reward "
                        "cooperation with Explorer Badges and stickers."
                    ),
                    "interaction": "Pair / Group",
                    "competency_materials": "Oral Production | Real-life prompt cards",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 6: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners note what helped them locate an answer and rate confidence."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket cards",
                },
            ],
        },
        {
            "id": "5ps-read-discover",
            "title": "I Read and Discover",
            "short_title": "I Read & Discover",
            "occurrence": "Section 1 Session 5 / Section 2 Session 4 (45 mn)",
            "domains": ["Written Comprehension", "Oral Production"],
            "guide_pages": "KS3 pp. 38-40, 44, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Lively fun game sounding topical words containing the section's target phonics."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Phonics / Written Comp. | Topical word cards",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 2: Presentation / Discovery (Install Resources)",
                    "procedure": (
                        "Briefly review the 'I Read and Understand' text; use leading questions and question cards "
                        "(who/what/where/when) so learners notice word boundaries, word order, SV agreement, "
                        "and punctuation IMPLICITLY (no grammar labels)."
                    ),
                    "interaction": "T-Ls / Ls-T",
                    "competency_materials": "Written Comprehension | Reading text, question cards",
                },
                {
                    "minutes": 15,
                    "stage": "Stage 3: Mechanical Practice — Controlled & Guided (Install Resources)",
                    "procedure": (
                        "Phase 1 Controlled: picture-prompt drilling for form. Phase 2 Guided: substitution, "
                        "gap-fill, and sentence anagram tasks in pairs/groups."
                    ),
                    "interaction": "Individual / Pair / Group",
                    "competency_materials": "Written / Oral Practice | Anagram cards, gap-fill board",
                },
                {
                    "minutes": 10,
                    "stage": "Stage 4: Communicative Practice / Assessment (Assessment)",
                    "procedure": (
                        "Personalized tasks (sentence completion, role-play, info-gap) with immediate feedback "
                        "to prevent fossilization; award Team Points."
                    ),
                    "interaction": "Pair / Group",
                    "competency_materials": "Oral / Written Practice | Info-gap cards, star chart",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 5: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners unscramble or complete one short sentence on their slate."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Slates, Exit Ticket",
                },
            ],
        },
        {
            "id": "5ps-learn-enjoy",
            "title": "I Learn and Enjoy",
            "short_title": "I Learn & Enjoy",
            "occurrence": "Section 1 Session 6 / Section 2 Session 5 (45 mn)",
            "domains": ["Oral Production", "Written Comprehension", "Written Production"],
            "guide_pages": "KS3 pp. 40-48, 53, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 10,
                    "stage": "Stage 1: Warm-up / Lacuna Activation (Warmer)",
                    "procedure": (
                        "Energetic starter game activating prior vocabulary/phonics and diagnosing observed "
                        "learning gaps (lacunas)."
                    ),
                    "interaction": "T-Ls / Group",
                    "competency_materials": "All Domains | Flashcards, slates",
                },
                {
                    "minutes": 30,
                    "stage": "Stage 2: Graded Reinforcement Games (Install Resources / Practice)",
                    "procedure": (
                        "Run a graded sequence (easy to challenging) of section-aligned classroom games: "
                        "Got it!, Snap!, Dictation Race, Slap the Board, Sentence Anagram, and Sound/Rhyme "
                        "challenges focusing on British English spelling with immediate feedback and Team Stars."
                    ),
                    "interaction": "Pair / Group / Team",
                    "competency_materials": "All Domains | Game cards, board markers, Explorer Badges",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 3: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners write one newly mastered British-English word and choose a "
                        "smiley reflecting their progress."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Slates, Exit Ticket chart",
                },
            ],
        },
        {
            "id": "5ps-learn-to-write",
            "title": "I Learn to Write",
            "short_title": "I Learn to Write",
            "occurrence": "Section 1 Session 7 / Section 2 Session 6 (45 mn)",
            "domains": ["Written Comprehension", "Written Production"],
            "guide_pages": "KS3 pp. 18-19, 49-50, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Quick punctuation and capitalization Slap-the-Board game reminding learners of "
                        "writing mechanics."
                    ),
                    "interaction": "T-Ls / Team",
                    "competency_materials": "Written Production | Mechanics cards, board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 2: Pre-write (Install Resources)",
                    "procedure": (
                        "Present a completed model form alongside its corresponding short message (~10/15/20 words) "
                        "and clarify the cooperative group task."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Model form & message poster",
                },
                {
                    "minutes": 22,
                    "stage": "Stage 3: Write — Modelling, Cooperative Drafting & Editing (Install Resources)",
                    "procedure": (
                        "Phase 1 Modelling for Imitation: use a second form, elicit note-to-sentence answers "
                        "orally, and check capitalization/punctuation/word order. Phase 2 Drafting: pair Q&A "
                        "then small-group drafting (writing for reinforcement) with gradual fading and linking. "
                        "Phase 3 Reviewing & Editing: group proofreading of mechanics."
                    ),
                    "interaction": "T-Ls / Pair / Small Group",
                    "competency_materials": "Written Production | Cue forms, group draft sheets",
                },
                {
                    "minutes": 8,
                    "stage": "Stage 4: Post-write — Publishing & Gallery Walk (Assessment)",
                    "procedure": (
                        "Small groups post their messages for a classroom Gallery Walk and read them aloud to peers; "
                        "teams earn Gold Stars and Explorer Badges."
                    ),
                    "interaction": "Group / Whole class",
                    "competency_materials": "Written & Oral Prod. | Display wall, stickers",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 5: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners record one mechanics rule they checked and any area needing help."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket slips",
                },
            ],
        },
        {
            "id": "5ps-write",
            "title": "I Write",
            "short_title": "I Write",
            "occurrence": "Section 1 Session 8 / Section 2 Session 7 (45 mn)",
            "domains": ["Written Production"],
            "guide_pages": "KS3 pp. 18-19, 51-52, 87",
            "requires_exit_ticket": True,
            "stages": [
                {
                    "minutes": 5,
                    "stage": "Stage 1: Warm-up (Warmer)",
                    "procedure": (
                        "Quick spot-the-mistake mechanics game motivating learners on capitalization, "
                        "full stops, and word order."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Sentence strips, board",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 2: Pre-write (Diagnostic)",
                    "procedure": (
                        "Present the individual form prompt, check comprehension of every form field, and "
                        "interactively recall the steps practiced in 'I Learn to Write'."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Written Production | Individual form prompt",
                },
                {
                    "minutes": 22,
                    "stage": "Stage 3: Write — Individual Drafting, Proofreading & Editing (Assessment)",
                    "procedure": (
                        "1) Individual drafting transforming form notes into a short message (~10/15/20 words) "
                        "while teacher monitors and collects anonymous error samples. 2) Silent self-proofreading. "
                        "3) Whole-class peer assessment on board sample sentences. 4) Final individual editing."
                    ),
                    "interaction": "Individual / T-Ls / Whole class",
                    "competency_materials": "Written Production | Copybooks, board error samples",
                },
                {
                    "minutes": 8,
                    "stage": "Stage 4: Post-write — Presentation & Peer Appreciation (Assessment)",
                    "procedure": (
                        "Selected learners read their final message aloud; peers show appreciation via "
                        "smiley/thumbs-up/traffic cards and earn stickers."
                    ),
                    "interaction": "Individual / Whole class",
                    "competency_materials": "Written & Oral Prod. | Smiley/traffic cards, stickers",
                },
                {
                    "minutes": 5,
                    "stage": "Stage 5: Feedback / Exit Ticket (Assessment)",
                    "procedure": (
                        "Exit Ticket: learners verbalize what they wrote, HOW they checked it, and what they enjoyed."
                    ),
                    "interaction": "Individual / T-Ls",
                    "competency_materials": "Formative Assessment | Exit Ticket cards",
                },
            ],
        },
        {
            "id": "5ps-check-progress",
            "title": "I Check My Progress",
            "short_title": "I Check My Progress",
            "occurrence": "End of Sequence (Section 2, Session 8 — 45 mn)",
            "domains": ["Oral Comprehension", "Written Comprehension", "Written Production"],
            "guide_pages": "KS3 pp. 28-29, 52, 70-71",
            "requires_exit_ticket": False,
            "stages": [
                {
                    "minutes": 12,
                    "stage": "Stage 1: Portfolio Retrieval & Listening Evaluation (Assessment)",
                    "procedure": (
                        "Learners retrieve their 'I Get Ready' answer sheets from personal portfolios; "
                        "teacher reads the listening script and administers the same listening tasks."
                    ),
                    "interaction": "T-Ls / Individual",
                    "competency_materials": "Oral Comprehension | Portfolio sheets, listening script",
                },
                {
                    "minutes": 13,
                    "stage": "Stage 2: Reading Evaluation (Assessment)",
                    "procedure": (
                        "Learners read the sequence evaluation text silently then aloud and complete the "
                        "overall-idea and detail-finding comprehension tasks."
                    ),
                    "interaction": "Individual",
                    "competency_materials": "Written Comprehension | Portfolio evaluation sheets",
                },
                {
                    "minutes": 13,
                    "stage": "Stage 3: Written Production Evaluation (Assessment)",
                    "procedure": (
                        "Learners read the form/chart and write the corresponding short message (~10/15/20 words) "
                        "demonstrating writing-mechanics progress."
                    ),
                    "interaction": "Individual",
                    "competency_materials": "Written Production | Portfolio evaluation sheets",
                },
                {
                    "minutes": 7,
                    "stage": "Stage 4: Sample Collection & Pause Remediation Prep (Assessment)",
                    "procedure": (
                        "Teacher collects portfolio sheets, selects samples across fast/average/slow learners, "
                        "and categorizes gaps for the upcoming 2-hour Pause remediation; praise effort with stickers."
                    ),
                    "interaction": "T-Ls",
                    "competency_materials": "Summative/Diagnostic | Learner portfolios, Pause checklist",
                },
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# 6. ACCESSOR HELPERS
# ---------------------------------------------------------------------------


def normalize_grade(grade: str) -> str:
    cleaned = (grade or "").strip().upper()
    aliases = {
        "3PS": "3PS",
        "YEAR 3": "3PS",
        "YEAR-3": "3PS",
        "3AP": "3PS",
        "4PS": "4PS",
        "YEAR 4": "4PS",
        "YEAR-4": "4PS",
        "4AP": "4PS",
        "5PS": "5PS",
        "YEAR 5": "5PS",
        "YEAR-5": "5PS",
        "5AP": "5PS",
    }
    if cleaned not in aliases:
        raise ValueError(f"Unsupported grade level: {grade!r}. Expected 3PS, 4PS, or 5PS.")
    return aliases[cleaned]


def get_grade_meta(grade: str) -> Dict[str, Any]:
    return copy.deepcopy(GRADE_META[normalize_grade(grade)])


def get_sequences(grade: str) -> List[Dict[str, Any]]:
    g = normalize_grade(grade)
    return copy.deepcopy(CURRICULUM_TREE[g]["sequences"])


def get_sequence_by_id(grade: str, sequence_id: str) -> Dict[str, Any]:
    for seq in get_sequences(grade):
        if seq["id"] == sequence_id or str(seq["number"]) == str(sequence_id):
            return seq
    raise ValueError(f"Sequence {sequence_id!r} not found for grade {grade!r}.")


def get_sections(grade: str, sequence_id: str) -> List[Dict[str, Any]]:
    seq = get_sequence_by_id(grade, sequence_id)
    return copy.deepcopy(seq["sections"])


def get_section_by_id(grade: str, sequence_id: str, section_id: str) -> Dict[str, Any]:
    for sec in get_sections(grade, sequence_id):
        if sec["id"] == section_id or str(sec["number"]) == str(section_id):
            return sec
    raise ValueError(
        f"Section {section_id!r} not found in sequence {sequence_id!r} for grade {grade!r}."
    )


def get_sessions(grade: str) -> List[Dict[str, Any]]:
    g = normalize_grade(grade)
    return copy.deepcopy(SESSION_BLUEPRINTS[g])


def get_session_blueprint(grade: str, session_id: str) -> Dict[str, Any]:
    for bp in get_sessions(grade):
        if bp["id"] == session_id or bp["title"].lower() == session_id.strip().lower():
            return bp
    raise ValueError(f"Session blueprint {session_id!r} not found for grade {grade!r}.")


# ---------------------------------------------------------------------------
# 7. SANITIZATION & PROMPT BUILDERS
# ---------------------------------------------------------------------------


def sanitize_non_monetary_gamification(text: str) -> str:
    """Replace any monetary reward references with child-safe classroom rewards."""
    result = text or ""
    for pattern, replacement in FORBIDDEN_MONETARY_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def scrub_learner_meta_terms(text: str) -> str:
    """Remove prohibited learner-facing didactic meta-terms (skim/scan/gist/prediction)."""
    result = text or ""
    for pattern, replacement in META_TERM_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def ensure_objective_formula(objective: str, fallback_action: str) -> str:
    """Ensure objective follows 'By the end of the session, learners will be able to ...'."""
    cleaned = (objective or "").strip()
    if not cleaned:
        return f"{OBJECTIVE_FORMULA_PREFIX} {fallback_action}"
    if cleaned.lower().startswith(OBJECTIVE_FORMULA_PREFIX.lower()):
        return OBJECTIVE_FORMULA_PREFIX + cleaned[len(OBJECTIVE_FORMULA_PREFIX):]
    cleaned_body = re.sub(
        r"^(?:learners\s+will\s+be\s+able\s+to|students\s+will\s+be\s+able\s+to|pupils\s+will\s+be\s+able\s+to|by\s+the\s+end\s+of\s+the\s+lesson,?\s*learners\s+will\s+be\s+able\s+to)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if not cleaned_body:
        cleaned_body = fallback_action
    if cleaned_body[0].isupper() and not cleaned_body.startswith(("I ",)):
        cleaned_body = cleaned_body[0].lower() + cleaned_body[1:]
    return f"{OBJECTIVE_FORMULA_PREFIX} {cleaned_body}"


def _parse_minutes(time_value: Any, default_minutes: int) -> int:
    if isinstance(time_value, int) and time_value > 0:
        return time_value
    if isinstance(time_value, str):
        m = re.search(r"(\d+)", time_value)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val
    return default_minutes


def _reconcile_stage_timings(
    stages: List[Dict[str, Any]],
    blueprint_stages: List[Dict[str, Any]],
    target_total: int = 45,
) -> List[Dict[str, Any]]:
    """Ensure stage minutes are positive integers that sum strictly to target_total minutes."""
    if not stages:
        stages = copy.deepcopy(blueprint_stages)

    minutes_list: List[int] = []
    for idx, st in enumerate(stages):
        fallback_min = (
            blueprint_stages[idx]["minutes"]
            if idx < len(blueprint_stages)
            else 5
        )
        raw_min = st.get("minutes", st.get("time", fallback_min))
        minutes_list.append(_parse_minutes(raw_min, fallback_min))

    current_total = sum(minutes_list)
    if current_total != target_total:
        if len(stages) == len(blueprint_stages):
            minutes_list = [bp["minutes"] for bp in blueprint_stages]
        elif current_total > 0:
            scaled = [max(1, round(m * target_total / current_total)) for m in minutes_list]
            diff = target_total - sum(scaled)
            # Adjust largest stage to hit exact target_total minutes
            max_idx = max(range(len(scaled)), key=lambda i: scaled[i])
            scaled[max_idx] = max(1, scaled[max_idx] + diff)
            minutes_list = scaled
        else:
            minutes_list = [target_total // len(stages)] * len(stages)
            minutes_list[0] += target_total - sum(minutes_list)

    normalized: List[Dict[str, Any]] = []
    for idx, st in enumerate(stages):
        mins = minutes_list[idx]
        bp_st = blueprint_stages[idx] if idx < len(blueprint_stages) else blueprint_stages[-1]
        stage_name = str(st.get("stage") or bp_st["stage"]).strip()
        proc_raw = str(st.get("procedure") or st.get("procedure_tasks") or bp_st["procedure"]).strip()
        proc_clean = sanitize_non_monetary_gamification(scrub_learner_meta_terms(proc_raw))
        interaction = str(st.get("interaction") or bp_st["interaction"]).strip()
        comp_mat = sanitize_non_monetary_gamification(
            str(st.get("competency_materials") or bp_st["competency_materials"]).strip()
        )
        normalized.append(
            {
                "minutes": mins,
                "time": f"{mins} mn",
                "stage": stage_name,
                "procedure": proc_clean,
                "interaction": interaction,
                "competency_materials": comp_mat,
            }
        )
    return normalized


def _extract_vocab_items(sec: Dict[str, Any], clean_topic: str) -> List[str]:
    """Flatten comma-separated vocabulary lists into individual target lexical items."""
    items: List[str] = []
    for entry in sec.get("key_vocabulary", []):
        for part in str(entry).split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
    if clean_topic and clean_topic not in items:
        items.insert(0, clean_topic)
    return items[:8] or [clean_topic or "target vocabulary"]


def _build_listening_script(
    grade: str,
    sec: Dict[str, Any],
    clean_topic: str,
    items: List[str],
) -> str:
    w1 = items[0]
    w2 = items[1] if len(items) > 1 else items[0]
    w3 = items[2] if len(items) > 2 else w1
    if grade == "3PS":
        return (
            f'Amine: "Hello, Lina! Look, {w1}!" | '
            f'Lina: "Hi, Amine! Is it {w2}?" | '
            f'Amine: "Yes! It is {w2} and {w3}." | '
            f'Lina: "Great! Let\'s say {w1}, {w2}, {w3}!"'
        )
    if grade == "4PS":
        return (
            f'Meriem: "Hello, Yacine! Welcome! Tell me about {clean_topic}." | '
            f'Yacine: "Look! Here we have {w1} and {w2}." | '
            f'Meriem: "Nice! Where is {w3}?" | '
            f'Yacine: "It is right here next to {w1}!"'
        )
    return (
        f'Amine: "Hi, Meriem! Today we are talking about {clean_topic}." | '
        f'Meriem: "Really? I know {w1} and {w2}!" | '
        f'Amine: "What about {w3}? Do you like it?" | '
        f'Meriem: "Yes, I do! It is very interesting."'
    )


def _build_reading_passage(
    grade: str,
    sec: Dict[str, Any],
    clean_topic: str,
    items: List[str],
) -> str:
    w1 = items[0]
    w2 = items[1] if len(items) > 1 else items[0]
    w3 = items[2] if len(items) > 2 else w2
    w4 = items[3] if len(items) > 3 else w1
    if grade == "3PS":
        return (
            f"Hello! I am Amine. This is {clean_topic}. "
            f"I see {w1} and {w2}. Look at {w3}. I like {w1}!"
        )
    if grade == "4PS":
        return (
            f"Hello! My name is Lina. I live in Algeria. Today our class talks about {clean_topic}. "
            f"We see {w1}, {w2}, and {w3}. My friend Amine likes {w4} very much."
        )
    target_words = int(sec.get("reading_word_target", 30) or 30)
    base = (
        f"Hello! I am Yacine from Blida. Today I am sharing notes about {clean_topic}. "
        f"Look at {w1}, {w2}, and {w3}. My friend Lina enjoys {w4} at the weekend."
    )
    if target_words >= 35:
        base += f" Together we ask and answer questions about {clean_topic} every day."
    return base


def _build_rich_stage_procedure(
    grade: str,
    seq: Dict[str, Any],
    sec: Dict[str, Any],
    bp: Dict[str, Any],
    stage_idx: int,
    stage_spec: Dict[str, Any],
    clean_topic: str,
) -> str:
    """
    Generate detailed, classroom-ready, multi-activity procedure text for every stage,
    with particular depth in 'Install Resources' stages (numbered activities, scripts,
    texts, forms, drills, answer keys, and T:/Ls: micro-interactions).
    """
    stage_name = stage_spec["stage"]
    stage_lower = stage_name.lower()
    bp_id = bp["id"]
    items = _extract_vocab_items(sec, clean_topic)
    w1 = items[0]
    w2 = items[1] if len(items) > 1 else w1
    w3 = items[2] if len(items) > 2 else w2
    w4 = items[3] if len(items) > 3 else w1
    vocab_preview = ", ".join(items[:6])
    grammar_preview = "; ".join(sec.get("implicit_grammar", []))
    phonics_target = sec.get("phonics_target", "target sounds")
    script = _build_listening_script(grade, sec, clean_topic, items)
    passage = _build_reading_passage(grade, sec, clean_topic, items)

    # 1. EXIT TICKET / FINAL FEEDBACK
    if "exit ticket" in stage_lower:
        return (
            f"Activity 1 (Ticket to Leave Check): Show 3 quick flashcards ({w1}, {w2}, {w3}) at the door/desks.\n"
            f'T: "Before we finish, name one word or phrase you learnt today and show your confidence card!"\n'
            f'Ls: Each pupil produces one target item/chunk for "{clean_topic}" and holds up a green/amber/red smiley card.\n'
            f"Activity 2 (Positive Closure): Award final Gold Stars and Stickers on the Team Chart for effort."
        )

    # 2. WARMER STAGES (Stage 1 of most sessions)
    if "i sing and have fun" in stage_lower:
        return (
            f"Activity 1 (Visual Song Introduction): Pin flashcards ({vocab_preview}) on the left board.\n"
            f"Activity 2 (Active Listening & TPR): Play/sing the '{seq['title']}' song twice. "
            f"Learners listen for rhythm and clap when they hear {w1} or {w2}.\n"
            f"Activity 3 (Whole-Class Sing-Along): Class sings together with mimes while teacher circulates to check pronunciation.\n"
            f'T: "Great rhythm, Team A and Team B! You earn 1 Gold Star each!"'
        )
    if "(warmer)" in stage_lower or stage_lower.startswith("stage 1: warm-up"):
        return (
            f"Activity 1 (Diagnostic Flashcard Game — 'Quick Flash'): Hold up 4 cards ({w1}, {w2}, {w3}, {w4}) for 2 seconds each.\n"
            f'T: "Look closely! What is this? Sound it out together!"\n'
            f'Ls: Name each card chorally and clap syllables/target sounds ({phonics_target}).\n'
            f"Activity 2 (Star Hook): Award Team Points on the right board to activate prior knowledge for '{clean_topic}'."
        )

    # 3. 3PS & 4PS SESSION 1 — I LISTEN & REPEAT
    if "listen-repeat" in bp_id:
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Visual Context — STRICTLY NO WRITTEN TEXT): Introduce '{clean_topic}' using flashcards, realia, and mimes only.\n"
                f"Activity 2 (Listening Script — 2 Clear Passes): Read/play the dialogue with expressive gestures:\n"
                f"Listening Script: {script}\n"
                f"Activity 3 (Oral Meaning Check): Ask 3 short yes/no and wh- questions using visuals:\n"
                f'T: "Show me {w1}! Is it {w2}? Point to {w3}!" | Ls: Point, mime, and reply orally ("Yes!" / "No!").'
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Choral -> Group -> Individual Drilling): Model '{w1}', '{w2}', '{w3}' in short chunks ({grammar_preview}). "
                f"Class repeats chorally, by rows, then individually with puppets.\n"
                f"Activity 2 (VC/CVC Phonemic Awareness — Oral Only): Say 4 target words slowly; learners isolate initial sound, "
                f"tap fingers to segment sounds, and clap hands to blend them back together (no sight words).\n"
                f"Activity 3 (Echo Star Challenge): Teacher whispers or mimes a chunk; teams echo accurately to earn Gold Stars & Explorer Badges."
            )

    # 4. 3PS & 4PS SESSION 2 — I READ & DISCOVER
    if "read-discover" in bp_id and grade in ("3PS", "4PS"):
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Left-to-Right Finger Tracking & Phonics): Display word cards ({w1}, {w2}, {w3}) and track left-to-right "
                f"focusing strictly on letter sounds ({phonics_target}), NOT letter names and NO sight words.\n"
                f"Activity 2 (Segmentation & Blending Drill): Model breaking target words sound-by-sound on board, then blend aloud with pupils.\n"
                f"Activity 3 (Short Text Discovery — ~{sec['reading_word_target']} words): Guide decoding of the reading card:\n"
                f'Reading Text: "{passage}"\n'
                f'T: "Put your finger under the first word. Sound it out together!" | Ls: Track and decode in pairs.'
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (VAKT Meaning Confirmation): Match decoded words ({w1}, {w2}, {w3}) to pictures and actions without translation.\n"
                f"Activity 2 (3-Sound Word & Sentence Strip Game): Each pair receives 4 word/phrase strips and 4 pictures to match in 4 minutes.\n"
                f"Activity 3 (Peer Reading Check): Pairs read 2 matched strips aloud to earn Explorer Badges and Team Points."
            )

    # 5. 4PS SESSION 3 — I READ & ENJOY (STRUCTURED GAMES)
    if bp_id == "4ps-read-enjoy":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Game Selection & Clear Rules): Introduce two inclusive reading games: 'Board Race' and 'Word Jumble Race'.\n"
                f"Game Rules: Teams line up calmly; 1 runner per turn reads a cue card, races to circle/build the word, and passes the marker.\n"
                f"Activity 2 (Volunteer Demonstration): Run 1 slow practice round with 2 pupils so every learner understands turn-taking and safety."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Game 1 — Board Race Reading): Teacher calls out clues for {w1}, {w2}, {w3}, {w4}; runners find and read the matching board card aloud.\n"
                f"Activity 2 (Game 2 — Word Jumble Race): Teams unscramble 4 jumbled topic words/chunks on desks (e.g., jumbled letters/word strips for '{clean_topic}').\n"
                f"Activity 3 (Game 3 — Mini-Pictionary & Pronunciation Check): Volunteers draw {w1} or {w2} while teams read & pronounce the answer to win Gold Stars & Explorer Badges."
            )

    # 6. 3PS SESSION 3 — I READ & WRITE (PRINT ONLY)
    if bp_id == "3ps-read-write":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Board Line Zones — Sky, Grass, Earth): Draw 4 handwriting lines on the center board and introduce "
                f"PRINT/script letter formation ({phonics_target}) — lowercase first, then UPPERCASE (NO cursive).\n"
                f"Activity 2 (Step-by-Step Stroke Modelling): Teacher traces large print letters slowly while counting strokes aloud.\n"
                f"Activity 3 (Air & Desk Tracing): Ls trace the shapes in the air and on desks with fingers before touching markers."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Guided Slate Practice): Learners write target print letters and 3 short words ({w1}, {w2}, {w3}) on lined slates; "
                f"teacher circulates checking sizing, spacing, and alignment.\n"
                f"Activity 2 (Independent Copybook Print Task): Pupils trace and copy 2 target words and 1 short print sentence "
                f"(e.g., 'It is {w1}.') checking capital letters and English '?' / '.' orientation (no free essay writing).\n"
                f"Activity 3 (Neatness Showcase): Best-aligned slates earn Gold Stars and Stickers."
            )

    # 7. 4PS SESSION 4 — I READ & WRITE (FORM COMPLETION IN CURSIVE)
    if bp_id == "4ps-read-write":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Session 2 Text Aloud Review): Re-display the Session 2 reading poster:\n"
                f'Reading Text: "{passage}"\n'
                f"Activity 2 (Word Bank Extraction): Learners read aloud in chunks and circle key words ({vocab_preview}) on the board for their form."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Topic Form Presentation): Display a large 'My {clean_topic} Card' model form on the center board:\n"
                f"Model Form: [ Name: ________ | Topic/Item: ________ | Detail: ________ | Favourite: ________ ]\n"
                f"Word Bank: {vocab_preview}\n"
                f'Activity 2 (Field Comprehension Check): T: "What do we write next to Name? Where do we put {w1}?" | Ls: Point and answer orally.'
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Cursive Join Demo): Model connected/joined (cursive) strokes on board lines (tall, short, and descender alignment).\n"
                f"Activity 2 (Individual Form Completion in Cursive): Learners select words from the Word Bank to complete their own 4-field form "
                f"in joined cursive handwriting (NOT free paragraph composition) while teacher monitors posture and joins.\n"
                f"Activity 3 (Partner Alignment Check): Pairs compare spacing and neatness; award Handwriting Gold Stars."
            )

    # 8. 3PS & 4PS PLAY ROLES
    if "play-roles" in bp_id:
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Model Dialogue with Puppets/Props): Act out the 4-line communicative scene:\n"
                f"Listening Script: {script}\n"
                f"Activity 2 (Scaffolded Rehearsal): Pair learners as Speaker A & Speaker B using picture cue cards and props "
                f"(focus on natural chunks and intonation, zero explicit grammar correction)."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Classroom Mini-Stage): 4–5 volunteer pairs perform the dialogue with props and gestures.\n"
                f"Activity 2 (Active Audience Task): Listening pupils hold up thumbs-up cards when they hear {w1} or {w2}.\n"
                f"Activity 3 (Reward Ceremony): Performers and attentive listeners earn Explorer Badges and Team Points."
            )

    # 9. 5PS — I LISTEN AND INTERACT
    if bp_id == "5ps-listen-interact":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Picture Walk): Display 3 visuals showing {w1}, {w2}, and {w3}; ask simple descriptive prompts.\n"
                f'T: "Look at the picture! Who do you see? What are they holding?"\n'
                f"Activity 2 (Think-Pair-Share): Pupils think silently for 30 seconds, share their initial guess with a partner, then share with class."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (First Listening Pass — Verify Guesses): Read/play the script once clearly:\n"
                f"Listening Script: {script}\n"
                f"Activity 2 (Self-Check & Class Confirmation): Learners raise green/red cards to confirm whether their initial guess matched."
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Second & Third Listening Passes): Play/read the script twice more with clear gestures and mimes (multiple listenings mandatory).\n"
                f"Activity 2 (Single Unambiguous Overall-Idea Task — True/False):\n"
                f"Task 1: Listen and circle True or False: 1) Meriem knows {w1}. (T/F)  2) They dislike {clean_topic}. (T/F)  3) Amine asks about {w3}. (T/F)\n"
                f"Answer Key: 1) True  2) False  3) True (encourage self-correction before confirming)."
            )
        if "stage 5" in stage_lower:
            return (
                f"Activity 1 (Personalized Pair Info-Gap): Pupils ask their partner 2 real-life questions using '{grammar_preview}' and note answers.\n"
                f'T: "Ask your partner about {w1} and {w2}! Listen carefully!" | Ls: Take turns interviewing in pairs.\n'
                f"Activity 2 (Mini-Report & Rewards): 3 pairs present their partner's answer to earn Team Points and Explorer Badges."
            )

    # 10. 5PS — I LISTEN AND DISCOVER
    if bp_id == "5ps-listen-discover":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Listening Script Recall): Re-read 2 key lines from:\n"
                f"Listening Script: {script}\n"
                f"Activity 2 (Oral Leading Questions — Implicit Discovery): Ask Who/What/Where questions so pupils notice word order "
                f"and subject-verb patterns ({grammar_preview}) implicitly — NEVER use grammatical terminology."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Phase 1 Controlled — Finger Word Boundaries & Hand Intonation): Model 3 target chunks counting each word on fingers "
                f"and sweeping hand up/down for question/statement intonation; class drills chorally and individually with immediate feedback.\n"
                f"Activity 2 (Phase 2 Guided Substitution Drill): Hold up cue cards ({w1}, {w2}, {w3}); pairs substitute new words into the frame dialogue.\n"
                f'T: "Card {w2}! Ask your partner!" | Ls: Pair exchange using correct rising/falling intonation.'
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Personalized Real-Life Role-Play): Pairs invent a 3-turn exchange about their own lives using {clean_topic}.\n"
                f'T: "Act out your own example with your partner!" | Ls: Perform short personalized exchanges.\n'
                f"Activity 2 (Supportive Feedback & Stars): Teacher gives gentle immediate recasts and awards Gold Stars."
            )

    # 11. 5PS — I READ AND UNDERSTAND
    if bp_id == "5ps-read-understand":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Topic Illustrations): Display pictures of {w1} and {w2}; ask learners to describe colours, people, and actions.\n"
                f'T: "Look at the picture! What can you see? Who is this?"\n'
                f"Activity 2 (Peer Guessing): Pairs share a 1-sentence initial guess about what the short text is about."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Silent Reading Verification): Learners read the ~{sec['reading_word_target']}-word text silently for 2 minutes to check their guesses.\n"
                f'Reading Text: "{passage}"\n'
                f"Activity 2 (Whole-Class Cross-Check): Pairs compare whether their guesses matched the text."
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Phase 1 Decoding & Meaningful Chunking): Teacher reads '{passage}' aloud with natural phrasing; pupils follow silently, "
                f"then 4 learners read aloud in meaningful chunks (focus on comprehension & phonics '{phonics_target}', NOT reading speed).\n"
                f"Activity 2 (Phase 2 Overall-Idea Task — 1 Activity): Circle the best title: A) My School Bag  B) {clean_topic}  C) Winter Holidays.\n"
                f"Activity 3 (Phase 2 Specific-Details Task — 1 Activity + Process Check): Complete the table [ Name: ____ | Items: ____ , ____ ].\n"
                f'T: "How did you find {w1}? Show me the exact line!" | Answer Key: Title B; Name: Yacine/Lina; Items: {w1}, {w2}, {w3}.'
            )
        if "stage 5" in stage_lower:
            return (
                f"Activity 1 (Real-Life Oral Connection): Pairs ask each other: 'Do you have/like {w1} or {w2}?' and share 1 sentence with their group.\n"
                f'T: "Tell your group about your partner!" | Ls: Share 1 real-life sentence aloud.\n'
                f"Activity 2 (Cooperation Rewards): Award Explorer Badges and Stickers for clear chunked reading and teamwork."
            )

    # 12. 5PS — I READ AND DISCOVER
    if bp_id == "5ps-read-discover":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Reading Text Recall & Question Cards): Display '{passage}' with Who / What / Where / When question cards.\n"
                f'T: "Look at the Who and What cards! Which word comes first in the sentence?" | Ls: Point to board chunks.\n'
                f"Activity 2 (Implicit Pattern Noticing): Highlight word boundaries, capital letters, punctuation, and '{grammar_preview}' via leading questions (no grammar rules)."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Phase 1 Controlled — Picture-Prompt Drilling): Show flashcards ({w1}, {w2}, {w3}); teams produce accurate full-sentence responses.\n"
                f"Activity 2 (Phase 2 Guided — Gap-Fill & Sentence Anagram): Groups complete 2 gap-fill sentences and unscramble 2 word-card anagrams:\n"
                f"Task 1: 1) I / {w1} / like / .   2) Look / {w2} / at / !   | Answer Key: 1) I like {w1}.  2) Look at {w2}!"
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Info-Gap & Role-Play): Pairs complete missing details on two split cue cards using target questions.\n"
                f'T: "Ask your partner to fill in the missing card item!" | Ls: Exchange questions and answers in pairs.\n'
                f"Activity 2 (Immediate Feedback Against Fossilization): Teacher circulates with gentle recasts and awards Team Points."
            )

    # 13. 5PS — I LEARN AND ENJOY
    if bp_id == "5ps-learn-enjoy":
        return (
            f"Activity 1 (Easy — 'Snap! & Slap the Board' British Spelling): Teams race to slap correct British-English spelling cards ({w1}, {w2}, {w3}, {w4}).\n"
            f"Activity 2 (Medium — 'Sentence Anagram Relay'): Groups reorder cut-up sentence strips matching '{grammar_preview}' in 6 minutes.\n"
            f"Activity 3 (Challenge — 'Dictation Race & Phonics Hunt'): Teacher models pronunciation before learners write 3 dictated words/chunks on slates; "
            f"award Gold Stars, Explorer Badges, and Team Points with immediate feedback."
        )

    # 14. 5PS — I LEARN TO WRITE (COOPERATIVE)
    if bp_id == "5ps-learn-to-write":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Model Form + Model Message): Display a completed sample form alongside its ~{sec['writing_word_target']}-word message:\n"
                f"Model Form: [ Name: Amine | Topic: {clean_topic} | Key Item: {w1} | Preference: {w2} ]\n"
                f'Model Message: "Hello! I am Amine. Today I talk about {clean_topic}. I like {w1} and {w2}."\n'
                f"Activity 2 (Goal Check): Clarify how each note in the form becomes one simple linked sentence."
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Phase 1 Modelling for Imitation): Display Form #2 ({w3}, {w4}); elicit each sentence orally with `T:` questions -> `Ls:` answers on board.\n"
                f"Activity 2 (Phase 2 Small-Group Cooperative Drafting & Linking): Pairs run Q&A on Form #3, then groups of 4 draft 3–4 simple sentences "
                f"(writing for reinforcement) and link them with capital letters and full stops while teacher gradually fades support.\n"
                f"Activity 3 (Phase 3 Group Proofreading & Editing): Groups self-check capitalization, full stops, spelling, and word order."
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Classroom Gallery Walk): Groups post their finished messages on the wall; teams rotate to read peers' work.\n"
                f'T: "Read your classmates\' posters and find one neat sentence!" | Ls: Circulate and give peer feedback.\n'
                f"Activity 2 (Aloud Showcase & Rewards): 3 groups read aloud and earn Gold Stars & Explorer Badges."
            )

    # 15. 5PS — I WRITE (INDIVIDUAL)
    if bp_id == "5ps-write":
        if "stage 2" in stage_lower:
            return (
                f"Activity 1 (Diagnostic Recall of Steps): Elicit the 3 steps practiced in 'I Learn to Write' (Read form -> Draft sentences -> Proofread mechanics).\n"
                f"Activity 2 (Individual Form Prompt Check): Display the target form [ Name | {clean_topic} | {w1} | {w2} ] and verify every field orally.\n"
                f'T: "What information goes in box 1? Don\'t forget capital letters!" | Ls: Identify each field aloud.'
            )
        if "stage 3" in stage_lower:
            return (
                f"Activity 1 (Individual Drafting): Each pupil transforms the form notes into a short ~{sec['writing_word_target']}-word message in their copybook "
                f"while teacher monitors and collects 3 anonymous sample mistakes on sticky notes.\n"
                f"Activity 2 (Silent Self-Proofreading): Learners check their own draft for capitals, full stops, and spelling.\n"
                f"Activity 3 (Board Peer Assessment & Final Editing): Write the 3 anonymous board samples; class spots and fixes errors together, then pupils edit their final copy."
            )
        if "stage 4" in stage_lower:
            return (
                f"Activity 1 (Aloud Presentation): 4 learners read their final edited message clearly.\n"
                f'T: "Listen to your classmate! Show green or smiley cards if the message is clear!"\n'
                f"Activity 2 (Peer Appreciation): Peers raise smiley/thumbs-up/traffic cards and award Classroom Stickers."
            )

    # 16. 5PS — I GET READY / I CHECK MY PROGRESS
    if bp_id in ("5ps-get-ready", "5ps-check-progress"):
        return (
            f"Activity 1 (Structured Portfolio Task — '{stage_name}'): {stage_spec['procedure']}\n"
            f"Sample Prompt Material ({clean_topic}): Script: {script} | Text: {passage}\n"
            f"Activity 2 (Portfolio Storage & Grouping): Collect/file sheets in learners' personal portfolios for progress comparison "
            f"(fast/average/slow group Pause diagnosis) and reward effort with Star Stickers."
        )

    # Fallback enriched procedure for any unmatched stage
    return (
        f"Activity 1 (Guided Presentation — '{clean_topic}'): {stage_spec['procedure']}\n"
        f"Target Lexis & Chunks: {vocab_preview} | {grammar_preview}\n"
        f'T: "Let\'s practice together!" | Ls: Work in {stage_spec["interaction"]} using flashcards and slates to earn Team Points.'
    )


def build_system_prompt(
    grade: str,
    sequence_id: str,
    section_id: str,
    session_id: str,
    topic: str,
) -> Tuple[str, str]:
    """
    Build the authoritative system prompt and user prompt encoding the extracted
    Algerian Didactic Guide rules and strict JSON output schema.
    """
    g = normalize_grade(grade)
    meta = get_grade_meta(g)
    duration_minutes = int(meta["session_duration_minutes"])
    seq = get_sequence_by_id(g, sequence_id)
    sec = get_section_by_id(g, sequence_id, section_id)
    bp = get_session_blueprint(g, session_id)
    clean_topic = (topic or "").strip() or sec["title"]

    constraints = PEDAGOGICAL_CONSTRAINTS["COMMON"] + PEDAGOGICAL_CONSTRAINTS[g]
    stages_guide = "\n".join(
        f"  {i + 1}. {s['stage']} ({s['minutes']} mn) | Interaction: {s['interaction']} | "
        f"Materials/Competency: {s['competency_materials']}\n     Guide Procedure: {s['procedure']}"
        for i, s in enumerate(bp["stages"])
    )

    system_prompt = (
        f"You are an expert Algerian Ministry of National Education Primary School English "
        f"Pedagogical Designer for AITADZ (aitadz.pro).\n"
        f"Generate a classroom-ready, 100% compliant {duration_minutes}-minute lesson plan strictly grounded in:\n"
        f"- {meta['guide_title']} ({meta['guide_year']}) | Level: {meta['label']}\n"
        f"- Project: {meta['project_title']}\n"
        f"- Handwriting & Writing Rule: {meta['handwriting_style']}\n\n"
        f"MANDATORY DIDACTIC CONSTRAINTS:\n"
        + "\n".join(f"- {c}" for c in constraints)
        + "\n\nINSTALL RESOURCES & ACTIVITY DEPTH REQUIREMENTS (CRITICAL):\n"
        "- Never write vague 1-sentence stage summaries (e.g., do NOT write just 'Read a short text' or 'Drill vocabulary').\n"
        "- Every 'Install Resources', Presentation, Discovery, Practice, Reading, Writing, or Game stage MUST include 2 to 3 numbered, concrete classroom activities separated by newlines ('Activity 1 (...): ...\\nActivity 2 (...): ...\\nActivity 3 (...): ...').\n"
        "- Include ready-to-teach classroom content directly inside 'procedure':\n"
        "  * For Listening stages: include the verbatim 4-line Listening Script (with Algerian pupil names) + 3 concrete oral comprehension questions + drilling/intonation steps.\n"
        "  * For Reading stages: include the verbatim level-calibrated Reading Text (~20-40 words) + phonics decoding words (segmentation/blending) + concrete comprehension tasks + Answer Key.\n"
        "  * For Writing stages: include exact letter formation families / model 4-field Form + Word Bank + Model Message + proofreading checklist.\n"
        "  * For Games / Role-Play stages: include explicit Game Rules, 4 concrete sample items/anagrams/cue cards, and Answer Key.\n"
        "- Include explicit 'T:' (Teacher script/prompts) and 'Ls:' (Expected learner actions/answers) inside stages.\n\n"
        "REQUIRED OUTPUT FORMAT:\n"
        "Return ONLY a single valid JSON object (no markdown fences) matching this exact structure:\n"
        "{\n"
        '  "header": {\n'
        '    "class_profile": "string",\n'
        '    "level": "string",\n'
        '    "number_of_learners": "string",\n'
        f'    "duration": "{duration_minutes} mn",\n'
        '    "sequence": "string",\n'
        '    "section": "string",\n'
        '    "session": "string",\n'
        '    "domains": "string",\n'
        '    "target_competence": "string",\n'
        '    "session_objectives": "By the end of the session, learners will be able to ...",\n'
        '    "subsidiary_objectives": "string",\n'
        '    "phonics_focus": "string",\n'
        '    "core_values": "string",\n'
        '    "cross_curricular_competencies": "string",\n'
        '    "teaching_materials": "string",\n'
        '    "anticipated_problems": "string",\n'
        '    "solutions_plan_b": "string"\n'
        "  },\n"
        '  "stages": [\n'
        "    {\n"
        '      "minutes": 15,\n'
        '      "time": "15 mn",\n'
        '      "stage": "exact official stage name",\n'
        '      "procedure": "Activity 1 (Context & Visuals): ...\\nListening Script / Reading Text / Model Form: ...\\nActivity 2 (Guided Practice / Task + Answer Key): ...\\nT: ... | Ls: ... (NO meta-terms like skim/scan/gist/prediction, NO explicit grammar lectures, NO monetary tokens)",\n'
        '      "interaction": "T-Ls / Pair / Individual / etc.",\n'
        '      "competency_materials": "Domain/Competency | VAKT Materials"\n'
        "    }\n"
        "  ],\n"
        '  "gamification": {\n'
        '    "title": "Non-monetary classroom reward mechanic",\n'
        '    "rewards": ["Gold Stars", "Explorer Badges", "Team Points", "Stickers"],\n'
        '    "description": "How child-appropriate classroom rewards motivate participation"\n'
        "  },\n"
        '  "exit_ticket": "End-of-session formative reflection task",\n'
        '  "whiteboard_layout": {\n'
        '    "left_panel": "Date, Sequence/Section/Session, Visual Flashcards & Target Vocabulary",\n'
        '    "center_panel": "Core Model Chunks / Text / Form / Phonics / Line Guides",\n'
        '    "right_panel": "Classroom Star & Team Points Tracker + Learner Slate Practice"\n'
        "  },\n"
        '  "self_reflection": {\n'
        '    "what_worked": "",\n'
        '    "what_hindered": "",\n'
        '    "action_plan": ""\n'
        "  }\n"
        "}"
    )

    if g == "4PS":
        writing_target_desc = "Form completion in cursive"
    elif g == "3PS":
        writing_target_desc = "Print letters/words only"
    else:
        writing_target_desc = f"~{sec['writing_word_target']} words from form notes"

    user_prompt = (
        f"Generate a complete, deeply detailed {duration_minutes}-minute Didactic-compliant lesson plan with these parameters:\n"
        f"- Grade: {g} ({meta['label']})\n"
        f"- Sequence {seq['number']}: {seq['title']} ({seq['guide_pages']})\n"
        f"- Section {sec['number']}: {sec['title']} ({sec['guide_pages']})\n"
        f"- Session: {bp['title']} ({bp['guide_pages']})\n"
        f"- Teacher's Specific Lesson Topic / Focus: {clean_topic}\n"
        f"- Official Communicative Objectives: {'; '.join(sec['communicative_objectives'])}\n"
        f"- Target Vocabulary: {', '.join(sec['key_vocabulary'])}\n"
        f"- Implicit Grammar Chunks: {'; '.join(sec['implicit_grammar'])}\n"
        f"- Phonics / Handwriting Target: {sec['phonics_target']}\n"
        f"- Reading Word Target: ~{sec['reading_word_target']} words | Writing Target: {writing_target_desc}\n\n"
        f"MANDATORY ORDERED STAGES (MUST SUM TO {duration_minutes} MINUTES, WITH 2-3 DETAILED ACTIVITIES IN EACH INSTALL RESOURCES STAGE):\n{stages_guide}\n"
    )

    return system_prompt, user_prompt


def build_default_lesson_plan(
    grade: str,
    sequence_id: str,
    section_id: str,
    session_id: str,
    topic: str = "",
) -> Dict[str, Any]:
    """
    Build a 100% Didactic-Guide-compliant deterministic lesson plan directly from
    the official Algerian curriculum tree and session blueprint.
    """
    g = normalize_grade(grade)
    meta = get_grade_meta(g)
    seq = get_sequence_by_id(g, sequence_id)
    sec = get_section_by_id(g, sequence_id, section_id)
    bp = get_session_blueprint(g, session_id)
    clean_topic = (topic or "").strip() or sec["title"].replace(f"Section {sec['number']}: ", "")

    primary_domain = bp["domains"][0] if bp["domains"] else "Oral Comprehension"
    target_comp = TARGET_COMPETENCIES[g].get(
        primary_domain, next(iter(TARGET_COMPETENCIES[g].values()))
    )
    comm_obj = "; ".join(sec["communicative_objectives"]).rstrip(".")
    vocab_str = ", ".join(sec["key_vocabulary"])
    grammar_str = "; ".join(sec["implicit_grammar"])

    if g == "3PS":
        subsidiary_obj = (
            f"Practice target phonics ({sec['phonics_target']}) and print/script mechanics "
            f"without explicit grammar rules."
        )
        anticipated = "Shyness during individual repetition; mixing print stroke direction or confusing similar sounds."
        plan_b = "Start with choral drilling and puppets before individual turns; model air-tracing step by step."
    elif g == "4PS":
        subsidiary_obj = (
            f"Recognize target sounds ({sec['phonics_target']}) and apply connected/joined "
            f"(cursive) alignment where writing is involved."
        )
        anticipated = "Hesitation in oral interaction or mixing print and cursive letter joins on forms."
        plan_b = "Use Think-Pair-Share and flashcard prompts; demonstrate cursive joins on board lines first."
    else:
        subsidiary_obj = (
            f"Notice word order and subject-verb agreement implicitly ({grammar_str}) "
            f"and reinforce target sounds ({sec['phonics_target']})."
        )
        anticipated = "Difficulty finding details in text or ordering words when transforming form notes into sentences."
        plan_b = "Model one example interactively on the board, use finger word-boundaries, and scaffold in pairs."

    stages: List[Dict[str, Any]] = []
    for st_idx, st in enumerate(bp["stages"]):
        rich_proc = _build_rich_stage_procedure(
            grade=g,
            seq=seq,
            sec=sec,
            bp=bp,
            stage_idx=st_idx,
            stage_spec=st,
            clean_topic=clean_topic,
        )
        stages.append(
            {
                "minutes": st["minutes"],
                "time": f"{st['minutes']} mn",
                "stage": st["stage"],
                "procedure": sanitize_non_monetary_gamification(scrub_learner_meta_terms(rich_proc)),
                "interaction": st["interaction"],
                "competency_materials": st["competency_materials"],
            }
        )

    exit_ticket = (
        "Ticket to Leave: Each learner shows a smiley/traffic card and shares one key word or phrase "
        f"about '{clean_topic}' before earning a Gold Star or Explorer Badge."
        if bp["requires_exit_ticket"]
        else "Portfolio Check: Learners file their answer sheets in personal portfolios and earn a Star Sticker for effort."
    )

    duration_minutes = int(meta["session_duration_minutes"])

    wb_items = _extract_vocab_items(sec, clean_topic)
    wb_lexis = ", ".join(wb_items[:6])
    wb_passage = _build_reading_passage(grade=g, sec=sec, clean_topic=clean_topic, items=wb_items)

    return {
        "meta": {
            "grade": g,
            "duration_minutes": duration_minutes,
            "sequence_id": seq["id"],
            "sequence_number": seq["number"],
            "sequence_title": seq["title"],
            "section_id": sec["id"],
            "section_number": sec["number"],
            "section_title": sec["title"],
            "session_id": bp["id"],
            "session_title": bp["title"],
            "topic": clean_topic,
            "guide_pages": f"{sec['guide_pages']} | {bp['guide_pages']}",
            "project_title": meta["project_title"],
        },
        "header": {
            "class_profile": f"{g} Primary Class",
            "level": meta["label"],
            "number_of_learners": "[To be completed by teacher]",
            "duration": f"{duration_minutes} mn",
            "sequence": f"Sequence {seq['number']}: {seq['title']}",
            "section": sec["title"],
            "session": f"{bp['title']} ({bp['occurrence']})",
            "domains": " / ".join(bp["domains"]),
            "target_competence": target_comp,
            "session_objectives": ensure_objective_formula(
                f"{comm_obj} in the context of {clean_topic}.",
                f"identify and use key language related to {clean_topic}.",
            ),
            "subsidiary_objectives": subsidiary_obj,
            "phonics_focus": f"{sec['phonics_target']} | Implicit focus: {grammar_str}",
            "core_values": (
                f"National Identity & Openness to the World: {CORE_VALUES['Citizenship']} "
                f"{CORE_VALUES['Openness to the World']}"
            ),
            "cross_curricular_competencies": (
                f"Intellectual & Methodological: {CROSS_CURRICULAR_COMPETENCIES['Intellectual']} | "
                f"Communicative & Social: {CROSS_CURRICULAR_COMPETENCIES['Personal and Social']}"
            ),
            "teaching_materials": (
                f"Flashcards ({clean_topic}), realia, audio/song track, whiteboard, "
                "learners' slates, Star & Explorer Badge reward chart."
            ),
            "anticipated_problems": anticipated,
            "solutions_plan_b": plan_b,
        },
        "stages": stages,
        "gamification": {
            "title": "AITADZ Non-Monetary Classroom Star & Explorer Quest",
            "rewards": list(ALLOWED_GAMIFICATION_REWARDS),
            "description": (
                f"Teams earn Team Points, Gold Stars, and Explorer Badges for active participation, "
                f"clear pronunciation, and respectful peer support during '{clean_topic}' tasks."
            ),
        },
        "exit_ticket": exit_ticket,
        "whiteboard_layout": {
            "left_panel": (
                f"Date: [Day, Date]\n"
                f"Seq {seq['number']}: {seq['title']} | {sec['title']}\n"
                f"Topic: {clean_topic}\n"
                f"Flashcards & Lexis:\n{wb_lexis}"
            ),
            "center_panel": (
                f"Session: {bp['short_title']}\n"
                f"Model Chunks / Prompts:\n{grammar_str}\n"
                f"Phonics / Mechanics:\n{sec['phonics_target']}\n"
                + (
                    "Note: NO written words on board during Session 1 Listen & Repeat!"
                    if g in ("3PS", "4PS") and "listen-repeat" in bp["id"]
                    else f"Model Text / Task:\n{wb_passage}"
                )
            ),
            "right_panel": (
                "Classroom Reward Board:\n"
                "- Team A: ★ ★ ★ (Explorer Badges)\n"
                "- Team B: ★ ★ ★ (Team Points)\n"
                f"Learner Slate Zone:\nTry: {wb_items[0]} | {wb_items[1] if len(wb_items) > 1 else clean_topic}\n"
                "[Teacher models & smiley check]"
            ),
        },
        "self_reflection": {
            "what_worked": "[To be completed by teacher after session]",
            "what_hindered": "[To be completed by teacher after session]",
            "action_plan": "[To be completed by teacher after session]",
        },
    }


def validate_and_normalize_lesson_plan(
    raw_data: Optional[Dict[str, Any]],
    grade: str,
    sequence_id: str,
    section_id: str,
    session_id: str,
    topic: str = "",
) -> Dict[str, Any]:
    """
    Validate an LLM/MCP JSON response against the Algerian Didactic Guide rules,
    reconciling missing header fields, enforcing the grade's official session
    duration (60 mn for 3PS/4PS, 45 mn for 5PS), scrubbing learner-facing
    meta-terms, and enforcing non-monetary classroom gamification.
    """
    baseline = build_default_lesson_plan(grade, sequence_id, section_id, session_id, topic)
    duration_minutes = int(baseline["meta"]["duration_minutes"])
    if not isinstance(raw_data, dict):
        return baseline

    result = copy.deepcopy(baseline)
    raw_header = raw_data.get("header") if isinstance(raw_data.get("header"), dict) else {}

    for key, default_val in baseline["header"].items():
        val = raw_header.get(key)
        if isinstance(val, str) and val.strip():
            cleaned = sanitize_non_monetary_gamification(val.strip())
            if key == "session_objectives":
                cleaned = ensure_objective_formula(cleaned, baseline["header"]["session_objectives"])
            elif key == "duration":
                cleaned = f"{duration_minutes} mn"
            result["header"][key] = cleaned

    # Always pin objective formula & official level duration
    result["header"]["duration"] = f"{duration_minutes} mn"
    result["header"]["session_objectives"] = ensure_objective_formula(
        result["header"]["session_objectives"],
        f"interact and practice language related to {result['meta']['topic']}.",
    )

    raw_stages = raw_data.get("stages")
    if isinstance(raw_stages, list) and len(raw_stages) > 0:
        valid_stages = [s for s in raw_stages if isinstance(s, dict)]
        if valid_stages:
            result["stages"] = _reconcile_stage_timings(
                valid_stages,
                baseline["stages"],
                target_total=duration_minutes,
            )

    # Gamification sanitization
    raw_gam = raw_data.get("gamification")
    if isinstance(raw_gam, dict):
        title = sanitize_non_monetary_gamification(str(raw_gam.get("title") or result["gamification"]["title"]))
        desc = sanitize_non_monetary_gamification(
            str(raw_gam.get("description") or result["gamification"]["description"])
        )
        rewards = raw_gam.get("rewards")
        if isinstance(rewards, list) and rewards:
            clean_rewards = [sanitize_non_monetary_gamification(str(r).strip()) for r in rewards if str(r).strip()]
        else:
            clean_rewards = list(ALLOWED_GAMIFICATION_REWARDS)
        result["gamification"] = {
            "title": title,
            "rewards": clean_rewards or list(ALLOWED_GAMIFICATION_REWARDS),
            "description": desc,
        }

    # Exit Ticket
    raw_exit = raw_data.get("exit_ticket")
    if isinstance(raw_exit, str) and raw_exit.strip():
        result["exit_ticket"] = sanitize_non_monetary_gamification(
            scrub_learner_meta_terms(raw_exit.strip())
        )

    # Whiteboard layout
    raw_wb = raw_data.get("whiteboard_layout")
    if isinstance(raw_wb, dict):
        for panel in ("left_panel", "center_panel", "right_panel"):
            val = raw_wb.get(panel)
            if isinstance(val, str) and val.strip():
                result["whiteboard_layout"][panel] = sanitize_non_monetary_gamification(
                    scrub_learner_meta_terms(val.strip())
                )

    # Self reflection
    raw_sr = raw_data.get("self_reflection")
    if isinstance(raw_sr, dict):
        for field in ("what_worked", "what_hindered", "action_plan"):
            val = raw_sr.get(field)
            if isinstance(val, str) and val.strip():
                result["self_reflection"][field] = val.strip()

    return result
