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
WARD_INFO = {
    1: {"name": "Upper Delaware", "side": "east",
        "north": 39.9565, "south": 39.9540, "west": -75.1479, "east": -75.1398},
    2: {"name": "Lower Delaware", "side": "east",
        "north": 39.9540, "south": 39.9521, "west": -75.1479, "east": -75.1398},
    3: {"name": "High Street", "side": "east",
        "north": 39.9521, "south": 39.9508, "west": -75.1479, "east": -75.1398},
    4: {"name": "Chestnut", "side": "east",
        "north": 39.9508, "south": 39.9484, "west": -75.1479, "east": -75.1398},
    5: {"name": "Walnut", "side": "east",
        "north": 39.9484, "south": 39.9465, "west": -75.1479, "east": -75.1398},
    6: {"name": "Dock", "side": "east",
        "north": 39.9465, "south": 39.9445, "west": -75.1479, "east": -75.1398},
    7: {"name": "New Market", "side": "east",
        "north": 39.9445, "south": 39.9385, "west": -75.1479, "east": -75.1398},
    8: {"name": "North Mulberry", "side": "west",
        "north": 39.9565, "south": 39.9540, "west": -75.1565, "east": -75.1479},
    9: {"name": "South Mulberry", "side": "west",
        "north": 39.9540, "south": 39.9521, "west": -75.1565, "east": -75.1479},
    10: {"name": "North", "side": "west",
         "north": 39.9521, "south": 39.9508, "west": -75.1565, "east": -75.1479},
    11: {"name": "Middle", "side": "west",
         "north": 39.9508, "south": 39.9484, "west": -75.1565, "east": -75.1479},
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
