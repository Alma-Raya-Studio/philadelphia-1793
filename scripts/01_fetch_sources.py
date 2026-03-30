#!/usr/bin/env python3
"""Download source files for the Carey Death List project.

Sources:
  1. Marjorie B. Winter's transcription of Carey's death list (usgwarchives.net)
  2. 1791 Biddle Directory spreadsheet (University of Delaware DSpace)
"""

import hashlib
import sys
from pathlib import Path

import requests

SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"

SOURCES = [
    {
        "name": "Carey death list transcription (Winter, 2005)",
        "url": "http://files.usgwarchives.net/pa/philadelphia/history/local/yfever1793/dead.txt",
        "filename": "raw_transcription.txt",
    },
    {
        "name": "1791 Biddle Directory (Smith/Sivitz MEAD dataset)",
        "url": "https://udspace.udel.edu/bitstreams/a712e9ae-1f15-471e-b8d1-62ff36dfefb1/download",
        "filename": "phil1791.xls",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(source: dict) -> Path:
    dest = SOURCES_DIR / source["filename"]
    if dest.exists():
        print(f"  Already exists: {dest.name} (SHA-256: {sha256(dest)})")
        return dest

    print(f"  Downloading {source['url']} ...")
    resp = requests.get(source["url"], timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  Saved: {dest.name} ({len(resp.content):,} bytes, SHA-256: {sha256(dest)})")
    return dest


def main():
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    ok = True
    for src in SOURCES:
        print(f"\n{src['name']}")
        try:
            fetch(src)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            ok = False
    if not ok:
        print("\nSome downloads failed. Re-run or download manually.", file=sys.stderr)
        sys.exit(1)
    print("\nAll sources downloaded successfully.")


if __name__ == "__main__":
    main()
