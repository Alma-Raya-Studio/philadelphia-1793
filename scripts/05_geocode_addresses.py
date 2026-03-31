#!/usr/bin/env python3
"""Geocode death list entries that have directory addresses.

Input:  data/carey_death_list_with_addresses.csv
        data/street_name_mapping.json
Output: data/carey_death_list_geocoded.csv
        data/geocoding_report.json

Uses grid-based interpolation of Philadelphia's 1790s street layout.
No external API calls needed - the grid is well-documented and largely intact.
"""

import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT / "data" / "carey_death_list_with_addresses.csv"
MAPPING_FILE = ROOT / "data" / "street_name_mapping.json"
OUTPUT_CSV = ROOT / "data" / "carey_death_list_geocoded.csv"
REPORT_FILE = ROOT / "data" / "geocoding_report.json"

# Bounding box for 1793 settled Philadelphia
BOUNDS = {
    "lat_min": 39.930,
    "lat_max": 39.965,
    "lng_min": -75.170,
    "lng_max": -75.135,
}

# Market Street latitude - divides N/S addresses on numbered streets
MARKET_LAT = 39.9508

# Delaware River longitude - house numbers on E-W streets increase going west
DELAWARE_LNG = -75.1393

# Approximate degrees per block (calibrated against modern basemap)
LAT_PER_BLOCK = 0.0018   # ~200m per block N-S
LNG_PER_BLOCK = 0.0021   # ~175m per block E-W

# House numbers per block (1790s Philadelphia used ~100 per block)
NUMBERS_PER_BLOCK = 100


def load_mapping():
    """Load the street name mapping file."""
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_address(address: str) -> dict:
    """Parse a directory address into components.

    Returns dict with keys: number, direction, street_name, addr_type.
    addr_type is one of: street, alley, court, lane, wharf, special.
    """
    address = address.strip()
    result = {
        "number": None,
        "direction": "",
        "street_name": address,
        "addr_type": "street",
    }

    # Classify address type
    lower = address.lower()
    if "alley" in lower:
        result["addr_type"] = "alley"
    elif "court" in lower:
        result["addr_type"] = "court"
    elif "lane" in lower:
        result["addr_type"] = "lane"
    elif "wharf" in lower or "wharves" in lower:
        result["addr_type"] = "wharf"

    # Extract leading number (handle "33 & 64 Sassafras St." - take first)
    m = re.match(r"^(\d+)\s*(?:&\s*\d+\s+)?(.+)$", address)
    if m:
        result["number"] = int(m.group(1))
        result["street_name"] = m.group(2).strip()

    return result


def geocode_street(parsed: dict, mapping: dict) -> dict:
    """Geocode a parsed street address using grid interpolation.

    Returns dict with latitude, longitude, method or None values.
    """
    street_name = parsed["street_name"]
    number = parsed["number"]

    # Look up in streets table
    streets = mapping.get("streets", {})
    info = streets.get(street_name)

    if not info:
        return {"latitude": None, "longitude": None, "method": "failed"}

    street_type = info["type"]

    if street_type == "ew":
        # East-west street: latitude is fixed, longitude varies by house number
        lat = info["latitude"]
        if number:
            # House numbers increase going west from the Delaware
            blocks_west = number / NUMBERS_PER_BLOCK
            lng = DELAWARE_LNG - (blocks_west * LNG_PER_BLOCK)
        else:
            # No number - place at approximate midpoint (3rd Street)
            lng = -75.1465
        return {"latitude": lat, "longitude": lng, "method": "grid_interpolation"}

    elif street_type == "ns":
        # North-south street: longitude is fixed, latitude varies by house number
        lng = info["longitude"]
        if number:
            blocks_from_market = number / NUMBERS_PER_BLOCK
            # Determine direction from street name prefix
            direction = ""
            if "N." in street_name or "N " in street_name:
                direction = "N"
            elif "S." in street_name or "S " in street_name:
                direction = "S"

            if direction == "S":
                lat = MARKET_LAT - (blocks_from_market * LAT_PER_BLOCK)
            else:
                # Default to north of Market
                lat = MARKET_LAT + (blocks_from_market * LAT_PER_BLOCK)
        else:
            lat = MARKET_LAT
        return {"latitude": lat, "longitude": lng, "method": "grid_interpolation"}

    return {"latitude": None, "longitude": None, "method": "failed"}


def geocode_alley_court(parsed: dict, mapping: dict) -> dict:
    """Geocode an alley, court, or lane using the lookup table."""
    street_name = parsed["street_name"]
    number = parsed["number"]

    # Check alleys
    alleys = mapping.get("alleys", {})
    if street_name in alleys:
        info = alleys[street_name]
        lat = info["latitude"]
        lng = info["longitude"]
        # Small offset for house numbers within the alley
        if number:
            offset = (number / 50) * 0.0003
            lat += offset
        return {"latitude": lat, "longitude": lng, "method": "alley_lookup"}

    # Check courts
    courts = mapping.get("courts", {})
    if street_name in courts:
        info = courts[street_name]
        lat = info["latitude"]
        lng = info["longitude"]
        if number:
            offset = (number / 20) * 0.0002
            lat += offset
        return {"latitude": lat, "longitude": lng, "method": "alley_lookup"}

    return {"latitude": None, "longitude": None, "method": "failed"}


def geocode_special(parsed: dict, mapping: dict) -> dict:
    """Geocode wharves and other special locations."""
    street_name = parsed["street_name"]
    # Try with the original full address too
    original = parsed.get("original", street_name)

    special = mapping.get("special", {})
    for key in [original, street_name]:
        if key in special:
            info = special[key]
            return {
                "latitude": info["latitude"],
                "longitude": info["longitude"],
                "method": "alley_lookup",
            }

    return {"latitude": None, "longitude": None, "method": "failed"}


def add_jitter(lat: float, lng: float, seed: int) -> tuple:
    """Add deterministic random jitter to prevent marker stacking."""
    rng = random.Random(seed)
    lat_jitter = rng.uniform(-0.0001, 0.0001)
    lng_jitter = rng.uniform(-0.0001, 0.0001)
    return lat + lat_jitter, lng + lng_jitter


def check_bounds(lat: float, lng: float) -> bool:
    """Check if coordinates fall within the 1793 settled area."""
    return (
        BOUNDS["lat_min"] <= lat <= BOUNDS["lat_max"]
        and BOUNDS["lng_min"] <= lng <= BOUNDS["lng_max"]
    )


def geocode_address(address: str, entry_id: int, mapping: dict) -> dict:
    """Geocode a single address. Main entry point.

    Returns dict with latitude, longitude, geocode_method.
    """
    parsed = parse_address(address)
    parsed["original"] = address

    # Route by address type
    if parsed["addr_type"] in ("alley", "court", "lane"):
        result = geocode_alley_court(parsed, mapping)
    elif parsed["addr_type"] in ("wharf", "special"):
        result = geocode_special(parsed, mapping)
    else:
        result = geocode_street(parsed, mapping)

    # If street lookup failed, try alley/special tables with full address
    if result["method"] == "failed":
        result = geocode_alley_court(parsed, mapping)
    if result["method"] == "failed":
        result = geocode_special(parsed, mapping)

    if result["latitude"] is not None:
        # Add jitter
        lat, lng = add_jitter(result["latitude"], result["longitude"], entry_id)
        result["latitude"] = round(lat, 6)
        result["longitude"] = round(lng, 6)

        # Bounds check
        if not check_bounds(result["latitude"], result["longitude"]):
            result["method"] = "failed"
            result["latitude"] = None
            result["longitude"] = None

    return {
        "latitude": result["latitude"] if result["latitude"] else "",
        "longitude": result["longitude"] if result["longitude"] else "",
        "geocode_method": result["method"],
    }


def main():
    print("Geocoding death list addresses...")

    # Check inputs
    for path, name in [
        (INPUT_CSV, "Enriched death list"),
        (MAPPING_FILE, "Street name mapping"),
    ]:
        if not path.exists():
            print(f"  {name} not found: {path}")
            print("  Run earlier pipeline steps first.")
            sys.exit(1)

    # Load data
    df = pd.read_csv(INPUT_CSV, dtype=str).fillna("")
    mapping = load_mapping()

    total = len(df)
    has_address = df[df["directory_address"] != ""]
    print(f"  {total} total entries")
    print(f"  {len(has_address)} entries with directory addresses")

    # Geocode
    print("\nGeocoding...")
    latitudes = []
    longitudes = []
    methods = []
    failed_addresses = []
    out_of_bounds = []

    for _, row in df.iterrows():
        address = row["directory_address"]
        entry_id = int(row["entry_id"]) if row["entry_id"] else 0

        if not address:
            latitudes.append("")
            longitudes.append("")
            methods.append("")
            continue

        result = geocode_address(address, entry_id, mapping)
        latitudes.append(result["latitude"])
        longitudes.append(result["longitude"])
        methods.append(result["geocode_method"])

        if result["geocode_method"] == "failed":
            failed_addresses.append(address)

    df["latitude"] = latitudes
    df["longitude"] = longitudes
    df["geocode_method"] = methods

    # Write output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\n  Wrote {OUTPUT_CSV}")

    # Summary
    geocoded = df[df["geocode_method"] != ""]
    succeeded = df[df["geocode_method"].isin(["grid_interpolation", "alley_lookup"])]
    failed = df[df["geocode_method"] == "failed"]
    by_method = geocoded[geocoded["geocode_method"] != ""]["geocode_method"].value_counts().to_dict()

    print(f"\n--- Geocoding Summary ---")
    print(f"  Entries with addresses: {len(has_address)}")
    print(f"  Successfully geocoded:  {len(succeeded)}")
    print(f"  Failed:                 {len(failed)}")
    for method, count in sorted(by_method.items()):
        print(f"    {method}: {count}")

    if failed_addresses:
        unique_failed = sorted(set(failed_addresses))
        print(f"\n  Failed addresses ({len(unique_failed)} unique):")
        for addr in unique_failed:
            print(f"    - {addr}")

    # Write report
    report = {
        "total_entries": total,
        "entries_with_address": len(has_address),
        "successfully_geocoded": len(succeeded),
        "failed": len(failed),
        "geocode_rate": round(len(succeeded) / len(has_address) * 100, 1)
        if len(has_address) > 0
        else 0,
        "by_method": by_method,
        "failed_addresses": sorted(set(failed_addresses)),
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {REPORT_FILE}")


if __name__ == "__main__":
    main()
