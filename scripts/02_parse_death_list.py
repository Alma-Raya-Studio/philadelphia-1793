#!/usr/bin/env python3
"""Parse the Winter transcription of Carey's death list into structured CSV.

Input:  sources/raw_transcription.txt
Output: data/carey_death_list.csv
        data/intermediate/parsed_raw.csv (before cleaning)
"""

import csv
import json
import re
import sys
from pathlib import Path

# Add parent to path so we can import utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.name_parser import (
    expand_abbreviation,
    extract_generational,
    extract_title,
    detect_origin,
    detect_relationship,
    is_occupation,
    parse_age,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sources" / "raw_transcription.txt"
OUTPUT_CSV = ROOT / "data" / "carey_death_list.csv"
OUTPUT_JSON = ROOT / "data" / "carey_death_list.json"
INTERMEDIATE = ROOT / "data" / "intermediate" / "parsed_raw.csv"


def read_transcription(path: Path) -> list[str]:
    """Read the transcription file and return entry lines only.

    Strips the header, footer, footnotes, blank lines, and `??` lines.
    """
    text = path.read_text(encoding="cp1252")
    lines = text.splitlines()

    entries = []
    in_list = False
    in_footnotes = False

    for line in lines:
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            continue

        # Skip `??` lines (transcriber uncertainty markers)
        if stripped == "??":
            continue

        # Detect start of the death list (first entry after header block)
        # The header ends with "Pages 121-159 of Carey's book."
        if "Pages 121-159" in stripped or "Pages 121–159" in stripped:
            in_list = True
            continue

        if not in_list:
            continue

        # Detect footnotes section (numbered notes at end)
        if re.match(r'^\d+\s+(Listed|Also|Poblick)', stripped):
            in_footnotes = True

        if in_footnotes:
            continue

        entries.append(stripped)

    return entries


def split_name_descriptor(line: str) -> tuple[str, str]:
    """Split a line into name portion and descriptor portion.

    The transcription uses several delimiter patterns:
      - " – " (en-dash with spaces)
      - " - " (hyphen with spaces, but NOT the hyphen in compound names)
      - ", " after the first name (when no dash delimiter)

    Returns (name_part, descriptor_part). descriptor_part may be empty.
    """
    # First try en-dash or em-dash
    for delim in [" – ", " — ", " - "]:
        # Only split on " - " if it's after the surname,firstname portion
        # i.e., after at least one comma
        if delim in line:
            idx = line.index(delim)
            # Make sure the delimiter is after the name (has at least one comma before it)
            before = line[:idx]
            if "," in before or delim != " - ":
                return before.strip(), line[idx + len(delim):].strip()

    # No dash delimiter — the descriptor (if any) follows after the name
    # Format: "Surname, FirstName, occupation" or "Surname, FirstName"
    return line, ""


def parse_entry(line: str, entry_id: int) -> dict:
    """Parse a single transcription line into a structured record."""
    record = {
        "entry_id": entry_id,
        "raw_text": line,
        "surname": "",
        "first_name": "",
        "first_name_expanded": "",
        "suffix": "",
        "occupation": "",
        "relationship_type": "",
        "related_to_name": "",
        "age": "",
        "origin": "",
        "descriptor": "",
        "additional_persons": "",
        "additional_persons_count": "",
        "entry_type": "named",
        "confidence": "high",
        "flags": [],
    }

    # --- Detect aggregate entries ---
    if re.search(r'\d+\s+names?\s+unknown', line, re.IGNORECASE):
        record["entry_type"] = "aggregate"
        match = re.search(r'(\d+)\s+names?\s+unknown', line, re.IGNORECASE)
        if match:
            record["additional_persons_count"] = match.group(1)
        # Extract the group label (e.g., "Sailors", "Servants")
        parts = re.split(r'\s*[–—-]\s*', line, maxsplit=1)
        record["descriptor"] = parts[0].strip()
        record["confidence"] = "medium"
        return record

    # --- Detect unnamed persons ---
    # Entries like "Sampson ___ – a Negro man" or "Jacob, a black man"
    if re.search(r'___+', line) or re.search(r'–-*\s*$', line.split(",")[0] if "," in line else ""):
        record["entry_type"] = "unnamed"
        record["confidence"] = "medium"

    # --- Split into name and descriptor ---
    name_part, desc_part = split_name_descriptor(line)

    # --- Parse the name portion ---
    # The name portion is typically: "Surname, FirstName" or "Surname, FirstName's relationship"
    # or just "Surname, FirstName"
    if "," in name_part:
        parts = name_part.split(",", 1)
        record["surname"] = parts[0].strip()
        remainder = parts[1].strip()
    else:
        # No comma — might be a single-name entry in the unnamed section
        record["surname"] = name_part.strip()
        remainder = ""

    # Clean up blanked-out names
    if re.match(r'^[_\-–—]+$', record["surname"]):
        record["surname"] = ""
        record["flags"].append("unknown_surname")

    # --- Handle "Widow" or "widow" as the start of remainder (relationship, not a name) ---
    if remainder.lower().strip() in ("widow", "widow."):
        record["relationship_type"] = "widow"
        remainder = ""
    elif re.match(r'^widow\b', remainder, re.IGNORECASE):
        # "widow and 2 children", "widow Bohn", etc.
        record["relationship_type"] = "widow"
        after_widow = re.sub(r'^widow\s*', '', remainder, flags=re.IGNORECASE).strip()
        if after_widow:
            add_match = re.match(r'(?:and|&)\s+(.*)', after_widow, re.IGNORECASE)
            if add_match:
                record["additional_persons"] = add_match.group(1).strip()
                count_match = re.search(r'(\d+)', record["additional_persons"])
                if count_match:
                    record["additional_persons_count"] = count_match.group(1)
            else:
                # Might be a name like "widow Bohn" — keep as related_to
                record["related_to_name"] = after_widow
        remainder = ""

    # --- Handle "wife of ?" patterns ---
    # e.g., "Alexander, wife of ?, & apprentice"
    wife_of_match = re.match(r'wife\s+of\s+(.+)', remainder, re.IGNORECASE)
    if wife_of_match:
        record["relationship_type"] = "wife"
        record["related_to_name"] = wife_of_match.group(1).strip().rstrip(",").strip()
        remainder = ""

    # --- Handle possessive relationships in the name portion ---
    # e.g., "James' wife", "Henry's child", "Robert's two children", "Jacob's daughter"
    elif not record["relationship_type"]:
        poss_match = re.match(
            r"(.+?)['']s?\s+(?:(\d+|two|three|four|five)\s+)?"
            r"(wife|children|child|daughters|daughter|son|apprentice|maid|coachman|young\s+\w+)",
            remainder, re.IGNORECASE
        )
        if poss_match:
            record["related_to_name"] = poss_match.group(1).strip()
            record["relationship_type"] = poss_match.group(3).lower()
            if poss_match.group(2):
                # "two children", "3 daughters", etc.
                count_text = poss_match.group(2)
                word_to_num = {"two": "2", "three": "3", "four": "4", "five": "5"}
                record["additional_persons_count"] = word_to_num.get(count_text.lower(), count_text)
            remainder_after = remainder[poss_match.end():].strip()
            if remainder_after:
                record["additional_persons"] = remainder_after.lstrip("and ").lstrip("& ").strip()
                count_match = re.search(r'(\d+)', record["additional_persons"])
                if count_match and not record["additional_persons_count"]:
                    record["additional_persons_count"] = count_match.group(1)
            remainder = ""

    # --- Handle "daughter of", "son of" patterns ---
    if not record["relationship_type"]:
        child_of_match = re.match(r'(daughter|son)\s+of\s+(.+)', remainder, re.IGNORECASE)
        if child_of_match:
            record["relationship_type"] = child_of_match.group(1).lower()
            record["related_to_name"] = child_of_match.group(2).strip()
            remainder = ""

    # --- Standard name + optional occupation parsing ---
    if remainder:
        # Extract title
        title, remainder = extract_title(remainder)
        if title:
            record["suffix"] = title

        # Extract generational suffix
        gen, remainder = extract_generational(remainder)
        if gen:
            record["suffix"] = (record["suffix"] + " " + gen).strip()

        # The first name is what remains
        # But it might include occupation info if there was no dash delimiter
        # e.g., "Adams, Moses, carpenter"
        if "," in remainder and not desc_part:
            fn_parts = remainder.split(",", 1)
            record["first_name"] = fn_parts[0].strip()
            desc_part = fn_parts[1].strip()
        else:
            record["first_name"] = remainder.strip()

    # Clean up blanked-out first names
    if re.match(r'^[_\-–—]+$', record["first_name"]):
        record["first_name"] = ""
        record["flags"].append("unknown_first_name")

    # --- Expand abbreviated first names ---
    expanded = expand_abbreviation(record["first_name"])
    record["first_name_expanded"] = expanded if expanded else record["first_name"]

    # --- Parse the descriptor portion ---
    if desc_part:
        # Check for age
        age = parse_age(desc_part)
        if age is not None:
            record["age"] = str(age)
            # Remove the age notation from desc
            desc_part = re.sub(r'(?:Æt|AEt|æt|aged?)\s*\d+', '', desc_part, flags=re.IGNORECASE).strip().strip(",").strip()

        # Check for origin
        origin = detect_origin(desc_part)
        if origin:
            record["origin"] = origin

        # Check for relationship
        rel = detect_relationship(desc_part)
        if rel:
            record["relationship_type"] = rel

        # Check for "and wife", "and child", "and 3 children", etc.
        add_match = re.search(r'(?:,\s*)?(?:&|and)\s+(his\s+)?(.+)', desc_part, re.IGNORECASE)
        if add_match:
            add_text = add_match.group(2).strip()
            # Only treat as additional persons if it mentions family/servants
            family_words = {"wife", "child", "children", "son", "daughter", "daughters",
                           "apprentice", "servant", "family"}
            if any(w in add_text.lower() for w in family_words):
                record["additional_persons"] = add_text
                count_match = re.search(r'(\d+)', add_text)
                if count_match:
                    record["additional_persons_count"] = count_match.group(1)
                # Remove the additional persons part from descriptor
                desc_part = desc_part[:add_match.start()].strip().rstrip(",").strip()

        # Check for "Widow" as standalone descriptor
        if desc_part.lower().strip() == "widow":
            record["relationship_type"] = "widow"
            desc_part = ""

        # What remains is likely the occupation
        # Clean it up
        occupation = desc_part.strip().rstrip(".")
        # Remove origin from occupation if present
        if record["origin"]:
            for orig in [record["origin"], record["origin"].lower(), "Fr.", "fr."]:
                occupation = occupation.replace(orig, "").strip().rstrip(",").strip()

        if occupation and occupation.lower() not in ("a", "an", "the", "and", "his"):
            record["occupation"] = occupation

        # Store full descriptor
        record["descriptor"] = desc_part

    # --- Handle entries that are clearly descriptive (unnamed section) ---
    # e.g., "Jacob, a black man" — first name only, descriptor in what we parsed as surname
    desc_indicators = ["a black", "a negro", "a mulatto", "a young", "servant girl",
                       "servant man", "servant boy"]
    full_lower = line.lower()
    for indicator in desc_indicators:
        if indicator in full_lower:
            if not record["relationship_type"]:
                record["entry_type"] = "unnamed"
            break

    # --- Confidence scoring ---
    if not record["surname"] and not record["first_name"]:
        record["confidence"] = "low"
    elif record["entry_type"] == "unnamed":
        record["confidence"] = "medium"
    elif len(record["flags"]) > 0:
        record["confidence"] = "medium"

    # Convert flags list to pipe-delimited string
    record["flags"] = "|".join(record["flags"]) if record["flags"] else ""

    return record


def main():
    if not SOURCE.exists():
        print(f"Source file not found: {SOURCE}")
        print("Run 01_fetch_sources.py first.")
        sys.exit(1)

    # Read and filter entries
    entries = read_transcription(SOURCE)
    print(f"Read {len(entries)} entry lines from transcription.")

    # Parse each entry
    records = []
    for i, line in enumerate(entries, start=1):
        record = parse_entry(line, entry_id=i)
        records.append(record)

    print(f"Parsed {len(records)} records.")

    # Write intermediate CSV (before cleaning)
    INTERMEDIATE.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_id", "raw_text", "surname", "first_name", "first_name_expanded",
        "suffix", "occupation", "relationship_type", "related_to_name",
        "age", "origin", "descriptor", "additional_persons",
        "additional_persons_count", "entry_type", "confidence", "flags",
    ]

    with open(INTERMEDIATE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote intermediate CSV: {INTERMEDIATE}")

    # Write final CSV (same for now — cleaning step can refine later)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote final CSV: {OUTPUT_CSV}")

    # Write JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"Wrote JSON: {OUTPUT_JSON}")

    # Summary statistics
    types = {}
    confidences = {}
    with_occupation = 0
    with_relationship = 0
    for r in records:
        types[r["entry_type"]] = types.get(r["entry_type"], 0) + 1
        confidences[r["confidence"]] = confidences.get(r["confidence"], 0) + 1
        if r["occupation"]:
            with_occupation += 1
        if r["relationship_type"]:
            with_relationship += 1

    print(f"\n--- Summary ---")
    print(f"Total records: {len(records)}")
    print(f"Entry types: {types}")
    print(f"Confidence: {confidences}")
    print(f"With occupation: {with_occupation}")
    print(f"With relationship: {with_relationship}")


if __name__ == "__main__":
    main()
