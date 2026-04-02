#!/usr/bin/env python3
"""Parse the 1789 Philadelphia Provincial Tax List and generate ward-level wealth data.

Input:  sources/1789_tax_list_sample.xls
        sources/occupational_codes.xlsx
Output: data/ward_wealth.json (ward stats + GeoJSON polygons for choropleth)

The 1789 tax list is an 80% random sample of Philadelphia's 11 city wards,
compiled by Billy G. Smith from the Philadelphia City Archives. It records
assessed property values for each taxpayer, providing a snapshot of wealth
distribution four years before the 1793 yellow fever epidemic.

Source: Smith, Billy G. "1789 TAX LIST OF PHILADELPHIA'S 11 WARDS."
Magazine of Early American Datasets (MEAD), University of Pennsylvania.
https://repository.upenn.edu/entities/dataset/c58ea7b3-7362-4f98-8854-13f72b54f434
License: CC-BY-4.0
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TAX_FILE = ROOT / "sources" / "1789_tax_list_sample.xls"
OCC_FILE = ROOT / "sources" / "occupational_codes.xlsx"
OUTPUT = ROOT / "data" / "ward_wealth.json"

# Ward names and boundaries from the Library Company of Philadelphia
# https://librarycompany.org/pos/wards.htm
# Boundaries defined by street intersections using Nominatim-derived coordinates
# Ward numbering from the codebook in sources/1789_tax_list_codebook.doc:
# 01=Chestnut, 02=Dock, 03=High St, 04=Lower Delaware, 05=Middle,
# 06=Mulberry, 07=North, 08=South, 10=Upper Delaware, 11=Walnut
# Ward 09 (New Market) is missing from the sample.

# Boundary coordinates calibrated against Nominatim/basemap
VINE = 39.9561
RACE = 39.9544
ARCH = 39.9535
MARKET = 39.9506
CHESTNUT = 39.9486
WALNUT = 39.9467
SPRUCE = 39.9450
SOUTH = 39.9395
FOURTH = -75.1473
RIVER = -75.1408
WEST = -75.1565

WARD_INFO = {
    # Eastern wards (Delaware River to 4th Street)
    10: {"name": "Upper Delaware", "side": "east",
         "north": VINE, "south": RACE, "west": FOURTH, "east": RIVER},
    4:  {"name": "Lower Delaware", "side": "east",
         "north": RACE, "south": ARCH, "west": FOURTH, "east": RIVER},
    3:  {"name": "High Street", "side": "east",
         "north": ARCH, "south": MARKET, "west": FOURTH, "east": RIVER},
    1:  {"name": "Chestnut", "side": "east",
         "north": MARKET, "south": CHESTNUT, "west": FOURTH, "east": RIVER},
    11: {"name": "Walnut", "side": "east",
         "north": CHESTNUT, "south": WALNUT, "west": FOURTH, "east": RIVER},
    2:  {"name": "Dock", "side": "east",
         "north": WALNUT, "south": SPRUCE, "west": FOURTH, "east": RIVER},
    9:  {"name": "New Market", "side": "east",
         "north": SPRUCE, "south": SOUTH, "west": FOURTH, "east": RIVER},
    # Western wards (4th Street to city limit)
    6:  {"name": "Mulberry", "side": "west",
         "north": VINE, "south": ARCH, "west": WEST, "east": FOURTH},
    7:  {"name": "North", "side": "west",
         "north": ARCH, "south": MARKET, "west": WEST, "east": FOURTH},
    5:  {"name": "Middle", "side": "west",
         "north": MARKET, "south": CHESTNUT, "west": WEST, "east": FOURTH},
    8:  {"name": "South", "side": "west",
         "north": CHESTNUT, "south": SOUTH, "west": WEST, "east": FOURTH},
}


def ward_to_geojson(ward_num: int) -> dict:
    """Create a GeoJSON polygon for a ward."""
    w = WARD_INFO[ward_num]
    # GeoJSON coordinates are [lng, lat] and must form a closed ring
    coords = [[
        [w["east"], w["south"]],   # SE corner
        [w["east"], w["north"]],   # NE corner
        [w["west"], w["north"]],   # NW corner
        [w["west"], w["south"]],   # SW corner
        [w["east"], w["south"]],   # close ring
    ]]
    return {
        "type": "Feature",
        "properties": {"ward": ward_num, "name": w["name"], "side": w["side"]},
        "geometry": {"type": "Polygon", "coordinates": coords},
    }


def main():
    print("Parsing 1789 Philadelphia Tax List...")

    for path, name in [(TAX_FILE, "1789 tax list"), (OCC_FILE, "Occupational codes")]:
        if not path.exists():
            print(f"  {name} not found: {path}")
            sys.exit(1)

    # Load tax data
    df = pd.read_excel(TAX_FILE)
    df.columns = ["surname", "first_name", "occ_code", "tax_assessment", "ward"]
    print(f"  {len(df)} tax entries loaded")

    # Load occupation codes
    occ_df = pd.read_excel(OCC_FILE)
    occ_df.columns = ["code", "occupation"]
    occ_map = dict(zip(occ_df["code"], occ_df["occupation"].str.strip()))

    # Decode occupations
    df["occupation"] = df["occ_code"].map(occ_map).fillna("UNKNOWN")

    # Compute ward-level statistics
    print("\n--- Ward Wealth Summary (1789 Provincial Tax) ---")
    print(f"{'Ward':<4} {'Name':<20} {'Count':>6} {'Median':>8} {'Mean':>8} {'Total':>10}")
    print("-" * 60)

    ward_data = []
    for ward_num in sorted(WARD_INFO.keys()):
        ward_df = df[df["ward"] == ward_num]
        info = WARD_INFO[ward_num]

        if len(ward_df) == 0:
            stats = {
                "count": 0, "median": 0, "mean": 0, "total": 0,
                "p25": 0, "p75": 0, "max": 0, "pct_zero": 0,
            }
            print(f"  {ward_num:<2} {info['name']:<20} {'(no data)':>6}")
        else:
            assessments = ward_df["tax_assessment"].values
            stats = {
                "count": int(len(ward_df)),
                "median": float(np.median(assessments)),
                "mean": round(float(np.mean(assessments)), 1),
                "total": int(np.sum(assessments)),
                "p25": float(np.percentile(assessments, 25)),
                "p75": float(np.percentile(assessments, 75)),
                "max": int(np.max(assessments)),
                "pct_zero": round(float(np.sum(assessments == 0) / len(assessments) * 100), 1),
            }
            print(f"  {ward_num:<2} {info['name']:<20} {stats['count']:>6} {stats['median']:>8.0f} {stats['mean']:>8.1f} {stats['total']:>10}")

        # Build GeoJSON feature with stats as properties
        feature = ward_to_geojson(ward_num)
        feature["properties"].update(stats)
        ward_data.append(feature)

    # Build output: GeoJSON FeatureCollection with ward stats
    output = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "1789 Philadelphia Provincial Tax List (80% sample)",
            "author": "Billy G. Smith",
            "repository": "https://repository.upenn.edu/entities/dataset/c58ea7b3-7362-4f98-8854-13f72b54f434",
            "license": "CC-BY-4.0",
            "note": "Ward 9 (South Mulberry) is missing from the sample. Suburbs of Northern Liberties and Southwark are not included.",
        },
        "features": ward_data,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
