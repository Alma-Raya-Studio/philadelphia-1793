"""Utilities for parsing 18th-century names, occupations, and relationships."""

import re

# Standard 18th-century first name abbreviations.
# These are well-documented conventions, not guesses.
NAME_ABBREVIATIONS = {
    "Jas.": "James",
    "Jas": "James",
    "Wm.": "William",
    "Wm": "William",
    "Tho's.": "Thomas",
    "Thos.": "Thomas",
    "Thos": "Thomas",
    "Tho.": "Thomas",
    "Jno.": "John",
    "Jno": "John",
    "Chas.": "Charles",
    "Chas": "Charles",
    "Benj.": "Benjamin",
    "Benj": "Benjamin",
    "Robt.": "Robert",
    "Robt": "Robert",
    "Richd.": "Richard",
    "Richd": "Richard",
    "Saml.": "Samuel",
    "Saml": "Samuel",
    "Danl.": "Daniel",
    "Danl": "Daniel",
    "Edwd.": "Edward",
    "Edwd": "Edward",
    "Geo.": "George",
    "Geo": "George",
    "Jos.": "Joseph",
    "Jos": "Joseph",
    "Jona.": "Jonathan",
    "Jona": "Jonathan",
    "Nathl.": "Nathaniel",
    "Nathl": "Nathaniel",
    "Alexr.": "Alexander",
    "Alexr": "Alexander",
    "Andw.": "Andrew",
    "Andw": "Andrew",
    "Christr.": "Christopher",
    "Christr": "Christopher",
    "Fredk.": "Frederick",
    "Fredk": "Frederick",
    "Phil.": "Philip",
    "Phil": "Philip",
}

# Titles and honorifics to extract as suffixes
TITLES = [
    "Rev.", "Capt.", "Col.", "Dr.", "Esq.", "Gen.", "Gov.",
    "Hon.", "Judge", "Lieut.", "Lt.", "Maj.", "Mr.", "Mrs.",
    "Sgt.", "Widow",
]

# Generational suffixes
GENERATIONAL = ["Jr.", "Jr", "Jun.", "Jun", "Sen.", "Sen", "Sr.", "Sr", "2d", "3d"]

# Relationship keywords
RELATIONSHIP_WORDS = {
    "wife", "child", "children", "son", "daughter", "daughters",
    "widow", "apprentice", "servant", "maid", "coachman",
}

# Known 18th-century occupations (partial list — extended during parsing)
OCCUPATIONS = {
    "baker", "barber", "blacksmith", "bookseller", "brewer", "bricklayer",
    "butcher", "cabinet-maker", "cardmaker", "carpenter", "chair-maker",
    "clerk", "coach-maker", "constable", "cooper", "coppersmith", "cordwainer",
    "currier", "distiller", "doctor", "druggist", "dyer", "engraver",
    "factor", "farmer", "fisherman", "founder", "glazier", "goldsmith",
    "grocer", "hairdresser", "hair-dresser", "hatter", "innkeeper",
    "joiner", "labourer", "laborer", "mariner", "mason", "merchant",
    "miller", "nailer", "painter", "physician", "pilot", "plasterer",
    "plumber", "porter", "potter", "printer", "rigger", "ropemaker",
    "sadler", "saddler", "sail-maker", "sailmaker", "sailor", "schoolmaster",
    "school-mistress", "seamstress", "shoemaker", "shopkeeper", "silversmith",
    "skinner", "smith", "soap-boiler", "stone-cutter", "sugar-baker",
    "surgeon", "tailor", "tanner", "tavern-keeper", "teacher", "tinner",
    "tobacconist", "turner", "type-founder", "upholsterer", "vendue-master",
    "vintner", "watchmaker", "weaver", "wheelwright", "whitesmith",
    "medical student", "servant girl", "servant man", "man-servant",
}

# Known countries/origins that appear in the list
ORIGINS = {
    "france", "fr.", "portugal", "ireland", "england", "germany",
    "scotland", "holland", "spain", "italy", "st. domingo",
    "santo domingo", "west indies",
}


def expand_abbreviation(name: str) -> str | None:
    """Expand a first name abbreviation. Returns None if no expansion found."""
    # Try exact match first
    if name in NAME_ABBREVIATIONS:
        return NAME_ABBREVIATIONS[name]
    # Try with period added
    if name + "." in NAME_ABBREVIATIONS:
        return NAME_ABBREVIATIONS[name + "."]
    return None


def extract_title(name_part: str) -> tuple[str | None, str]:
    """Extract a title/honorific from the beginning of a name string.

    Returns (title, remaining_string).
    """
    for title in TITLES:
        if name_part.startswith(title + " ") or name_part.startswith(title + "."):
            return title.rstrip("."), name_part[len(title):].strip()
        # Handle "Widow" as a standalone descriptor
        if title == "Widow" and name_part.startswith("Widow "):
            return "Widow", name_part[6:].strip()
    return None, name_part


def extract_generational(name_part: str) -> tuple[str | None, str]:
    """Extract Jr., Sen., etc. from a name string.

    Returns (suffix, remaining_string).
    """
    for gen in GENERATIONAL:
        pattern = r'\b' + re.escape(gen) + r'\.?\b'
        match = re.search(pattern, name_part, re.IGNORECASE)
        if match:
            cleaned = name_part[:match.start()].strip().rstrip(",") + " " + name_part[match.end():].strip()
            return gen.rstrip("."), cleaned.strip()
    return None, name_part


def is_occupation(text: str) -> bool:
    """Check if a string looks like an occupation."""
    return text.lower().strip().rstrip(".") in OCCUPATIONS


def detect_relationship(text: str) -> str | None:
    """Detect relationship type from descriptor text.

    Returns the relationship type or None.
    """
    t = text.lower()
    if "'s wife" in t or "wife" in t.split():
        return "wife"
    if "'s child" in t or "child" in t.split():
        return "child"
    if "'s son" in t or "son" in t.split():
        return "son"
    if "'s daughter" in t or "daughter" in t.split():
        return "daughter"
    if "children" in t:
        return "children"
    if "daughters" in t:
        return "daughters"
    if "widow" in t.split():
        return "widow"
    if "apprentice" in t:
        return "apprentice"
    if "servant" in t:
        return "servant"
    if "maid" in t:
        return "maid"
    if "coachman" in t:
        return "coachman"
    return None


def detect_origin(text: str) -> str | None:
    """Detect a country/place of origin from descriptor text."""
    t = text.lower().strip().rstrip(".")
    for origin in ORIGINS:
        if origin in t:
            # Return the canonical form
            if origin == "fr.":
                return "France"
            return origin.title()
    return None


def parse_age(text: str) -> int | None:
    """Extract age from 'AEt 70' or 'Æt 70' or 'aged 72' notation."""
    match = re.search(r'(?:Æt|AEt|æt|aged?)\s*(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def normalize_name(name) -> str:
    """Normalize a name for matching: lowercase, strip punctuation, collapse whitespace."""
    if not isinstance(name, str):
        return ""
    name = name.lower().strip()
    name = re.sub(r'[.,;:\'"()]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name
