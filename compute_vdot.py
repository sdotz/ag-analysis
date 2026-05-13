#!/usr/bin/env python3
"""Script to compute VDOT scores for race performance CSV files and add them as a new column.

Uses the Jack Daniels VDOT formula directly, which works for any distance:
  v       = distance_meters / time_minutes  (velocity in m/min)
  vo2     = -4.60 + 0.182258*v + 0.000104*v^2
  pct_max = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
  VDOT    = vo2 / pct_max
"""

import math
import os
import pandas as pd

# Exact race distances in meters, keyed by the prefix in each filename
# (filename format: "<key>-Table 1.csv")
DISTANCE_METERS = {
    'Mile':     1609.34,
    '5K':       5000.0,
    '8k':       8000.0,
    '8K':       8000.0,
    '10K':     10000.0,
    '12K':     12000.0,
    '15K':     15000.0,
    '10 Mile': 16093.4,
    '20K':     20000.0,
    '25K':     25000.0,
    '30K':     30000.0,
    'H Mar':   21097.5,
    'Marathon':42195.0,
}


def vdot_from_race(distance_m, time_sec):
    """Compute VDOT from race distance (metres) and time (seconds)."""
    t = time_sec / 60.0                     # minutes
    v = distance_m / t                       # metres / minute
    vo2     = -4.60 + 0.182258 * v + 0.000104 * v ** 2
    pct_max = (0.8
               + 0.1894393 * math.exp(-0.012778  * t)
               + 0.2989558 * math.exp(-0.1932605 * t))
    return round(vo2 / pct_max, 1)


def extract_distance_key(filename):
    return filename.replace('-Table 1.csv', '').strip()


def compute_vdot_for_file(filepath):
    filename = os.path.basename(filepath)
    distance_key = extract_distance_key(filename)

    if distance_key not in DISTANCE_METERS:
        print(f"Warning: no distance entry for '{distance_key}' ({filename})")
        return False

    dist_m = DISTANCE_METERS[distance_key]
    df = pd.read_csv(filepath)

    vdot_scores = []
    for _, row in df.iterrows():
        time_sec = row['TIME_SEC']
        if pd.isna(time_sec) or time_sec <= 0:
            vdot_scores.append(None)
        else:
            vdot_scores.append(vdot_from_race(dist_m, float(time_sec)))

    df['VDOT'] = vdot_scores
    df.to_csv(filepath, index=False)

    n = sum(1 for v in vdot_scores if v is not None)
    print(f"✓ {filename}  ({n} scores, distance={dist_m:.1f} m)")
    return True


def main():
    import sys
    msab_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'msab', 'men')
    csv_files = sorted(f for f in os.listdir(msab_dir) if f.endswith('.csv'))

    print(f"Processing {len(csv_files)} CSV files in {msab_dir}...\n")
    ok = sum(compute_vdot_for_file(os.path.join(msab_dir, f)) for f in csv_files)
    print(f"\nDone: {ok}/{len(csv_files)} files updated.")


if __name__ == '__main__':
    main()
