#!/usr/bin/env python3
"""Cross-reference the death list with the 1791 Biddle Directory to add addresses.

Input:  data/carey_death_list.csv
        data/intermediate/directory_parsed.csv
Output: data/carey_death_list_with_addresses.csv

Matching strategy (tiered by confidence):
  1. Exact: surname + first_name + occupation  → "exact"
  2. Name+occ: surname + occupation (first name missing) → "name_occupation"
  3. Name only: surname + first_name → "name_only"
  4. Fuzzy: rapidfuzz on surname + first_name → "fuzzy"
  5. Relationship: for "wife of X" entries, look up X → "relationship"
"""

import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent.parent
DEATH_LIST = ROOT / "data" / "carey_death_list.csv"
DIRECTORY = ROOT / "data" / "intermediate" / "directory_parsed.csv"
OUTPUT = ROOT / "data" / "carey_death_list_with_addresses.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.name_parser import normalize_name

FUZZY_THRESHOLD = 85  # Minimum fuzzy match score

# Occupation synonyms — terms that refer to the same trade
OCCUPATION_SYNONYMS = {
    "shoemaker": "cordwainer",
    "cordwainer": "shoemaker",
    "sadler": "saddler",
    "saddler": "sadler",
    "labourer": "laborer",
    "laborer": "labourer",
    "stonecutter": "stone cutter",
    "stone cutter": "stonecutter",
    "stone-cutter": "stonecutter",
    "hairdresser": "hair dresser",
    "hair dresser": "hairdresser",
    "hair-dresser": "hairdresser",
    "innkeeper": "tavern keeper",
    "tavern keeper": "innkeeper",
    "tavern-keeper": "innkeeper",
    "shopkeeper": "shop keeper",
    "shop keeper": "shopkeeper",
    "sailmaker": "sail maker",
    "sail maker": "sailmaker",
    "sail-maker": "sailmaker",
    "cabinet-maker": "cabinet maker",
    "cabinet maker": "cabinet-maker",
    "coach-maker": "coach maker",
    "coach maker": "coach-maker",
    "soap-boiler": "soap boiler",
    "soap boiler": "soap-boiler",
    "sugar-baker": "sugar baker",
    "sugar baker": "sugar-baker",
    "chair-maker": "chair maker",
    "chair maker": "chair-maker",
}


def build_directory_index(dir_df: pd.DataFrame) -> dict:
    """Build lookup indices from the directory DataFrame."""
    index = {
        "by_surname_first_occ": {},  # (surname, first, occ) -> row
        "by_surname_first": {},       # (surname, first) -> [rows]
        "by_surname_occ": {},         # (surname, occ) -> [rows]
        "by_surname": {},             # surname -> [rows]
    }

    for idx, row in dir_df.iterrows():
        sn = row.get("surname_normalized", "")
        fn = row.get("first_name_normalized", "")
        occ = row.get("occupation_normalized", "")

        if sn and fn and occ:
            key = (sn, fn, occ)
            index["by_surname_first_occ"][key] = row

        if sn and fn:
            key = (sn, fn)
            if key not in index["by_surname_first"]:
                index["by_surname_first"][key] = []
            index["by_surname_first"][key].append(row)

        if sn and occ:
            key = (sn, occ)
            if key not in index["by_surname_occ"]:
                index["by_surname_occ"][key] = []
            index["by_surname_occ"][key].append(row)

        if sn:
            if sn not in index["by_surname"]:
                index["by_surname"][sn] = []
            index["by_surname"][sn].append(row)

    return index


def get_address(row: pd.Series) -> str:
    """Extract address from a directory row."""
    if "address" in row.index and row["address"]:
        return str(row["address"])
    return ""


def match_entry(death_row: pd.Series, index: dict, dir_df: pd.DataFrame) -> dict:
    """Try to match a death list entry against the directory.

    Returns dict with match info or empty match.
    """
    result = {
        "directory_name": "",
        "directory_address": "",
        "directory_occupation": "",
        "match_confidence": "",
        "match_method": "",
    }

    sn = normalize_name(str(death_row.get("surname", "")))
    # Prefer expanded first name (Jas. -> James)
    fn_raw = str(death_row.get("first_name_expanded", "") or death_row.get("first_name", ""))
    fn = normalize_name(fn_raw)
    occ = normalize_name(str(death_row.get("occupation", "")))
    # Get synonym for occupation
    occ_syn = normalize_name(OCCUPATION_SYNONYMS.get(occ, ""))

    if not sn:
        return result

    # --- Tier 1: Exact match on surname + first_name + occupation ---
    if fn and occ:
        for try_occ in [occ, occ_syn]:
            if not try_occ:
                continue
            key = (sn, fn, try_occ)
            if key in index["by_surname_first_occ"]:
                row = index["by_surname_first_occ"][key]
                result["directory_name"] = f"{row.get('surname', '')}, {row.get('first_name', '')}"
                result["directory_address"] = get_address(row)
                result["directory_occupation"] = str(row.get("occupation", ""))
                result["match_confidence"] = "high"
                result["match_method"] = "exact"
                return result

    # --- Tier 2: Surname + first_name ---
    if fn:
        key = (sn, fn)
        if key in index["by_surname_first"]:
            matches = index["by_surname_first"][key]
            if len(matches) == 1:
                row = matches[0]
                result["directory_name"] = f"{row.get('surname', '')}, {row.get('first_name', '')}"
                result["directory_address"] = get_address(row)
                result["directory_occupation"] = str(row.get("occupation", ""))
                result["match_confidence"] = "medium"
                result["match_method"] = "name_only"
                return result
            elif len(matches) > 1 and occ:
                # Multiple people with same name — try to disambiguate by occupation
                for row in matches:
                    row_occ = normalize_name(str(row.get("occupation", "")))
                    if row_occ == occ or (occ_syn and row_occ == occ_syn):
                        result["directory_name"] = f"{row.get('surname', '')}, {row.get('first_name', '')}"
                        result["directory_address"] = get_address(row)
                        result["directory_occupation"] = str(row.get("occupation", ""))
                        result["match_confidence"] = "high"
                        result["match_method"] = "exact"
                        return result

    # --- Tier 3: Relationship lookup ---
    # For "wife of X" or "child of X", look up X in the directory
    related = str(death_row.get("related_to_name", ""))
    rel_type = str(death_row.get("relationship_type", ""))
    if related and rel_type in ("wife", "child", "son", "daughter", "children", "daughters"):
        related_fn = normalize_name(related)
        key = (sn, related_fn)
        if key in index["by_surname_first"]:
            matches = index["by_surname_first"][key]
            row = matches[0]  # Take first match
            result["directory_name"] = f"{row.get('surname', '')}, {row.get('first_name', '')} ({rel_type})"
            result["directory_address"] = get_address(row)
            result["directory_occupation"] = str(row.get("occupation", ""))
            result["match_confidence"] = "medium"
            result["match_method"] = "relationship"
            return result

    # --- Tier 4: Fuzzy match on surname + first_name ---
    if fn and sn in index["by_surname"]:
        candidates = index["by_surname"][sn]
        if candidates:
            best_score = 0
            best_row = None
            for row in candidates:
                cand_fn = str(row.get("first_name_normalized", ""))
                score = fuzz.ratio(fn, cand_fn)
                if score > best_score:
                    best_score = score
                    best_row = row

            if best_score >= FUZZY_THRESHOLD and best_row is not None:
                result["directory_name"] = f"{best_row.get('surname', '')}, {best_row.get('first_name', '')}"
                result["directory_address"] = get_address(best_row)
                result["directory_occupation"] = str(best_row.get("occupation", ""))
                result["match_confidence"] = "low"
                result["match_method"] = f"fuzzy ({best_score})"
                return result

    return result


def main():
    for path, name in [(DEATH_LIST, "death list"), (DIRECTORY, "directory")]:
        if not path.exists():
            print(f"{name} not found: {path}")
            print("Run earlier pipeline steps first.")
            sys.exit(1)

    print("Loading death list...")
    death_df = pd.read_csv(DEATH_LIST, dtype=str).fillna("")
    print(f"  {len(death_df)} entries")

    print("Loading directory...")
    dir_df = pd.read_csv(DIRECTORY, dtype=str).fillna("")
    print(f"  {len(dir_df)} entries")

    print("Building directory index...")
    index = build_directory_index(dir_df)

    print("Matching entries...")
    match_results = []
    for _, row in death_df.iterrows():
        match = match_entry(row, index, dir_df)
        match_results.append(match)

    # Merge results
    match_df = pd.DataFrame(match_results)
    result_df = pd.concat([death_df.reset_index(drop=True), match_df], axis=1)

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT, index=False, encoding="utf-8")
    print(f"\nWrote {len(result_df)} entries to {OUTPUT}")

    # Summary
    matched = (result_df["match_method"] != "").sum()
    print(f"\n--- Match Summary ---")
    print(f"Total death list entries: {len(result_df)}")
    print(f"Matched to directory: {matched} ({matched/len(result_df)*100:.1f}%)")
    print(f"\nBy method:")
    for method in result_df["match_method"].value_counts().index:
        if method:
            count = (result_df["match_method"] == method).sum()
            print(f"  {method}: {count}")
    print(f"\nBy confidence:")
    for conf in ["high", "medium", "low"]:
        count = (result_df["match_confidence"] == conf).sum()
        if count:
            print(f"  {conf}: {count}")
    unmatched = (result_df["match_method"] == "").sum()
    print(f"  unmatched: {unmatched}")


if __name__ == "__main__":
    main()
