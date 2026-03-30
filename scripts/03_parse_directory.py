#!/usr/bin/env python3
"""Parse the 1791 Biddle Directory (Smith/Sivitz MEAD dataset) into a lookup table.

Input:  sources/phil1791.xls
Output: data/intermediate/directory_parsed.csv

The exact column layout of the XLS file is unknown until we inspect it.
This script reads the file, prints column info, normalizes names, and outputs
a clean lookup table for address matching.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sources" / "phil1791.xls"
OUTPUT = ROOT / "data" / "intermediate" / "directory_parsed.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.name_parser import normalize_name


def inspect_xls(path: Path) -> pd.DataFrame:
    """Read the XLS file and print diagnostic info about its structure."""
    # Try reading with different engines
    try:
        df = pd.read_excel(path, engine="xlrd")
    except Exception:
        df = pd.read_excel(path)

    print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nFirst 5 rows:")
    print(df.head().to_string())
    print(f"\nColumn dtypes:")
    print(df.dtypes)
    print(f"\nNull counts:")
    print(df.isnull().sum())
    return df


def normalize_directory(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the directory DataFrame for matching.

    This function will need to be adjusted based on the actual column names
    in the XLS file. It attempts to auto-detect common column name patterns.
    """
    # Map common column name patterns to our standard names
    col_map = {}
    for col in df.columns:
        cl = str(col).lower().strip()
        if "surname" in cl or "last" in cl or cl == "name":
            col_map[col] = "surname"
        elif "first" in cl or "given" in cl or "christian" in cl:
            col_map[col] = "first_name"
        elif "occup" in cl or "trade" in cl or "profession" in cl:
            col_map[col] = "occupation"
        elif "address" in cl or "street" in cl or "resid" in cl or "dwelling" in cl:
            col_map[col] = "address"
        elif "lat" in cl:
            col_map[col] = "latitude"
        elif "lon" in cl or "lng" in cl:
            col_map[col] = "longitude"

    if col_map:
        print(f"\nAuto-detected column mapping: {col_map}")
        df = df.rename(columns=col_map)
    else:
        print("\nWARNING: Could not auto-detect column names. Manual mapping needed.")
        print("Columns found:", list(df.columns))

    # Ensure required columns exist
    required = ["surname", "first_name"]
    for req in required:
        if req not in df.columns:
            print(f"\nERROR: Required column '{req}' not found.")
            print(f"Available columns: {list(df.columns)}")
            print("Please update the column mapping in this script.")
            sys.exit(1)

    # Combine Str Number + Street into address if both exist
    if "Str Number" in df.columns and "address" in df.columns:
        df["address"] = (
            df["Str Number"].fillna("").astype(str).str.strip() + " " +
            df["address"].fillna("").astype(str).str.strip()
        ).str.strip()
    elif "Str Number" in df.columns and "address" not in df.columns:
        df["address"] = df["Str Number"].fillna("").astype(str).str.strip()

    # Normalize text fields
    for col in ["surname", "first_name", "occupation", "address"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
            df[col] = df[col].replace("nan", "")

    # Add normalized name columns for matching
    df["surname_normalized"] = df["surname"].apply(normalize_name)
    df["first_name_normalized"] = df["first_name"].apply(normalize_name)
    if "occupation" in df.columns:
        df["occupation_normalized"] = df["occupation"].apply(normalize_name)

    return df


def main():
    if not SOURCE.exists():
        print(f"Source file not found: {SOURCE}")
        print("Run 01_fetch_sources.py first.")
        sys.exit(1)

    print("=== Inspecting 1791 Biddle Directory ===\n")
    df = inspect_xls(SOURCE)

    print("\n=== Normalizing ===\n")
    df = normalize_directory(df)

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, encoding="utf-8")
    print(f"\nWrote {len(df)} directory entries to {OUTPUT}")

    # Summary
    if "address" in df.columns:
        with_addr = (df["address"] != "").sum()
        print(f"Entries with addresses: {with_addr} ({with_addr/len(df)*100:.1f}%)")
    if "occupation" in df.columns:
        with_occ = (df["occupation"] != "").sum()
        print(f"Entries with occupations: {with_occ} ({with_occ/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
