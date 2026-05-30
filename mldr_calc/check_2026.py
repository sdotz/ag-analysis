"""
Re-compute AP% for every GP performance in a given year using the official
MLDR 2025 calculator and compare against the AP% recorded in the source CSV.

    python check_2026.py            # checks 2026 (default)
    python check_2026.py 2025
"""

import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mldr import age_grade


# Default: 2026. Override with CLI arg ("2025", "2024", "2023").
YEAR = sys.argv[1] if len(sys.argv) > 1 else "2026"

CSV_BY_YEAR = {
    "2023": ("2023MAUSATF",     "All-Table 1.csv"),
    "2024": ("2024MAUSATF",     "All-Table 1.csv"),
    "2025": ("2025MAUSATF",     "All-Table 1.csv"),
    "2026": ("2026MAUSATF",     "All Races-Table 1.csv"),
}
if YEAR not in CSV_BY_YEAR:
    sys.exit(f"Unknown year {YEAR}; expected one of {list(CSV_BY_YEAR)}")

sub, fname = CSV_BY_YEAR[YEAR]
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "gp-scores", sub, fname)

# Race name → distance (km). Covers every name seen across 2023-2026.
RACE_DIST_KM = {
    "ADR 5K":                    5.0,
    "Adrenaline 5k":             5.0,
    "Main Line 5k":              5.0,
    "Main Street Mile":          1.609344,
    "Frostbite 5 Mile":          8.04672,
    "Frostbite 5 Miler":         8.04672,
    "Revolutionary 5 Miler":     8.04672,
    "Red Rose 5 Miler":          8.04672,
    "Scott Coffee":              8.04672,
    "Rothmans 8k":               8.0,
    "Ben Franklin Bridge 10k":  10.0,
    "Delaware Distance Classic":15.0,
    "Broad Street":             16.09344,
    "PDR":                      21.0975,
    "Philly Half":              21.0975,
    "Philly Marathon":          42.195,
}

# Threshold: source AP% in the CSV is published to 3 decimal places.
# Calculator outputs differ at most by floating-point + 3-dp rounding.
TOL = 0.05   # report anything off by > 0.05 percentage points


def main():
    matches = 0
    near = 0
    flagged = []
    missing_race = Counter()

    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            race = row["Race"].strip()
            dist_km = RACE_DIST_KM.get(race)
            if dist_km is None:
                missing_race[race] += 1
                continue

            try:
                h = int(row["HH"] or 0)
                m = int(row["MM"] or 0)
                s = int(row["SS"] or 0)
                age = int(row["AGE"])
                gender = row["G"].strip().upper()
                csv_ap = float(row["AP%"])
            except (KeyError, ValueError):
                continue

            time_sec = h * 3600 + m * 60 + s
            if time_sec <= 0:
                continue

            res = age_grade(dist_km, time_sec, age, gender, year=2025)
            if res is None:
                flagged.append({
                    "name": f"{row['First Name']} {row['Last Name']}",
                    "race": race, "time": f"{h}:{m:02d}:{s:02d}",
                    "age": age, "gender": gender,
                    "csv_ap": csv_ap, "calc_ap": None, "diff": None,
                    "note": "calculator returned None",
                })
                continue

            calc_ap = res.ap_pct
            diff = calc_ap - csv_ap
            if abs(diff) <= 0.005:        # essentially identical
                matches += 1
            elif abs(diff) <= TOL:        # within rounding wobble
                near += 1
            else:
                flagged.append({
                    "name": f"{row['First Name']} {row['Last Name']}",
                    "race": race, "time": f"{h}:{m:02d}:{s:02d}",
                    "age": age, "gender": gender,
                    "csv_ap": csv_ap, "calc_ap": calc_ap, "diff": diff,
                    "factor": res.factor, "note": "",
                })

    total = matches + near + len(flagged) + sum(missing_race.values())
    print(f"Year: {YEAR}    Checked {total} rows")
    print(f"  exact match (|diff| ≤ 0.005)    : {matches}")
    print(f"  near match  (≤ {TOL})            : {near}")
    print(f"  FLAGGED     (> {TOL})            : {len(flagged)}")
    if missing_race:
        print(f"  unmapped race names              : {dict(missing_race)}")

    if not flagged:
        print("\nNo discrepancies above tolerance.")
        return

    # Sort flagged by absolute diff desc
    flagged.sort(key=lambda r: -(abs(r["diff"]) if r["diff"] is not None else 1e9))

    print(f"\n--- Top flagged rows (|diff| > {TOL}) ---")
    print(f"{'Name':<28} {'G':<2} {'Age':>3} {'Race':<22} {'Time':>9} "
          f"{'CSV AP%':>8} {'Calc AP%':>8} {'Diff':>7}")
    print("-" * 100)
    for r in flagged[:60]:
        diff_str = f"{r['diff']:+.3f}" if r['diff'] is not None else "  N/A "
        calc_str = f"{r['calc_ap']:.3f}" if r['calc_ap'] is not None else "  N/A "
        note = ("  " + r["note"]) if r.get("note") else ""
        print(f"{r['name']:<28} {r['gender']:<2} {r['age']:>3} {r['race']:<22} "
              f"{r['time']:>9} {r['csv_ap']:>8.3f} {calc_str:>8} {diff_str:>7}{note}")

    if len(flagged) > 60:
        print(f"...and {len(flagged) - 60} more flagged rows")


if __name__ == "__main__":
    main()
