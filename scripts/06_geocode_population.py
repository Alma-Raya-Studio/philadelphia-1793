#!/usr/bin/env python3
"""Geocode the full 1791 Biddle Directory and assign flight probabilities.

Input:  data/intermediate/directory_parsed.csv
        data/street_name_mapping.json
Output: data/population_geocoded.csv

Reuses geocoding functions from 05_geocode_addresses.py.
Assigns a flight_probability (0-1) to each entry based on occupation
and location, modeling who fled the 1793 epidemic and who stayed.

METHODOLOGY NOTE:
The flight_probability is a STATISTICAL MODEL, not individual-level data.
We do not have records of who specifically fled and when. What we know:
- ~20,000 of ~45,000 residents fled between late August and mid-October 1793
- The wealthy and well-connected fled first (documented in contemporary accounts)
- Government officials fled in early-to-mid September
- The poor, enslaved, and free Black community largely stayed
- Richard Allen and Absalom Jones organized Black Philadelphians to nurse the sick

The flight_probability score models these patterns using occupation as a proxy
for socioeconomic status and longitude as a proxy for neighborhood wealth
(western blocks were wealthier, eastern waterfront blocks were poorer).
The visualization assigns departure periods proportionally so that the
aggregate percentages match historical estimates, but individual departures
are simulated, not documented.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pathlib import Path as _  # noqa - force module reload context

# Import geocoding functions from the existing script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "geocode", ROOT / "scripts" / "05_geocode_addresses.py"
)
geocode_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geocode_mod)

geocode_address = geocode_mod.geocode_address
load_mapping = geocode_mod.load_mapping

INPUT_CSV = ROOT / "data" / "intermediate" / "directory_parsed.csv"
OUTPUT_CSV = ROOT / "data" / "population_geocoded.csv"

# Occupation flight tiers (normalized occupation -> probability)
HIGH_FLIGHT = {
    "merchant", "merchants", "gentleman", "gentlewoman", "esquire",
    "attorney at law", "broker", "importer", "doctor of physic",
    "physician", "counsellor at law", "judge",
}

MEDIUM_HIGH_FLIGHT = {
    "shopkeeper", "grocer", "innkeeper", "tobacconist", "schoolmaster",
    "schoolmistress", "printer", "apothecary", "bookseller", "druggist",
    "stationer", "dry goods", "hardware", "conveyancer",
}

MEDIUM_FLIGHT = {
    "taylor", "baker", "butcher", "hatter", "cooper", "joiner",
    "house carpenter", "bricklayer", "painter", "cabinet maker",
    "cabinetmaker", "silversmith", "clockmaker", "watchmaker",
    "tanner", "sadler", "coach maker", "tinsmith", "upholsterer",
}

LOW_FLIGHT = {
    "labourer", "mariner", "sailor", "carter", "porter",
    "washerwoman", "servant", "boardinghouse", "widow", "spinster",
    "huckster shop", "ship carpenter", "cordwainer", "weaver",
    "barber", "blacksmith", "skindresser", "oysterman", "fisherman",
}


def get_flight_probability(occupation: str, lng: float) -> float:
    """Compute flight probability based on occupation and location."""
    occ = occupation.lower().strip()

    # Base probability by occupation tier
    # Tuned so that at 43% flight (peak), wealthy areas are visibly empty
    # and working-class areas remain visibly populated
    if occ in HIGH_FLIGHT:
        base = 0.92
    elif occ in MEDIUM_HIGH_FLIGHT:
        base = 0.72
    elif occ in MEDIUM_FLIGHT:
        base = 0.50
    elif occ in LOW_FLIGHT:
        base = 0.15
    elif occ == "":
        base = 0.45
    else:
        base = 0.48

    # Location modifier: wealthier west, poorer east
    # Stronger modifier to create visible geographic contrast
    if lng < -75.149:  # West of 4th Street
        base *= 1.3
    elif lng > -75.143:  # East of 2nd Street
        base *= 0.7

    return max(0.0, min(1.0, base))


def main():
    print("Geocoding 1791 Biddle Directory for population layer...")

    if not INPUT_CSV.exists():
        print(f"  Directory data not found: {INPUT_CSV}")
        print("  Run scripts/03_parse_directory.py first.")
        sys.exit(1)

    df = pd.read_csv(INPUT_CSV, dtype=str).fillna("")
    mapping = load_mapping()
    print(f"  {len(df)} directory entries loaded")

    has_address = df[df["address"] != ""]
    print(f"  {len(has_address)} entries with addresses")

    print("\nGeocoding...")
    results = []
    failed_streets = {}

    for idx, row in df.iterrows():
        address = row["address"]
        if not address:
            continue

        entry_id = idx + 10000  # Offset to avoid jitter collision with death list
        result = geocode_address(address, entry_id, mapping)

        if result["geocode_method"] == "failed":
            # Track failed street names
            import re
            m = re.match(r"^\d+\s*(&\s*\d+\s+)?(.+)$", address.strip())
            street = m.group(2).strip() if m else address.strip()
            failed_streets[street] = failed_streets.get(street, 0) + 1
            continue

        lat = float(result["latitude"])
        lng = float(result["longitude"])
        occ = row.get("occupation_normalized", row.get("occupation", ""))
        flight_prob = get_flight_probability(occ, lng)

        name = f"{row['surname']}, {row['first_name']}".strip(", ")
        results.append({
            "name": name,
            "occupation": occ,
            "address": address,
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "geocode_method": result["geocode_method"],
            "flight_probability": round(flight_prob, 3),
        })

    out_df = pd.DataFrame(results)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\n  Wrote {OUTPUT_CSV}")

    print(f"\n--- Population Geocoding Summary ---")
    print(f"  Total directory entries:  {len(df)}")
    print(f"  With addresses:           {len(has_address)}")
    print(f"  Successfully geocoded:    {len(results)}")
    print(f"  Failed:                   {len(has_address) - len(results)}")

    if failed_streets:
        top_fails = sorted(failed_streets.items(), key=lambda x: -x[1])[:15]
        print(f"\n  Top failed street names ({len(failed_streets)} unique):")
        for street, count in top_fails:
            print(f"    {count:4d}  {street}")

    # Flight probability distribution
    probs = [r["flight_probability"] for r in results]
    high = sum(1 for p in probs if p >= 0.7)
    med = sum(1 for p in probs if 0.3 <= p < 0.7)
    low = sum(1 for p in probs if p < 0.3)
    print(f"\n  Flight probability distribution:")
    print(f"    High (>=0.7):  {high}")
    print(f"    Medium:        {med}")
    print(f"    Low (<0.3):    {low}")


if __name__ == "__main__":
    main()
