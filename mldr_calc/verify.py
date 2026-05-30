"""
Verification: run a handful of known cases against mldr.py and print results.
"""

from mldr import age_grade, parse_time, format_time, DISTANCES_KM


CASES = [
    # (label, dist_km, time_str, age, gender, year)
    ("Thomas Jennings — 82M road mile 7:32",
     DISTANCES_KM["1mi"], "7:32", 82, "M", 2025),

    ("Open-age M road mile WR 3:47 (expect ~100%)",
     DISTANCES_KM["1mi"], "3:47", 25, "M", 2025),

    ("Open-age F road mile WR 4:13 (expect ~100%)",
     DISTANCES_KM["1mi"], "4:13", 28, "F", 2025),

    ("M 5K @ 12:49 age 25 (expect ~100%)",
     DISTANCES_KM["5k"], "12:49", 25, "M", 2025),

    ("M marathon 2:00:35 age 25 (expect ~100%)",
     DISTANCES_KM["marathon"], "2:00:35", 25, "M", 2025),

    ("M marathon 3:00:00 age 40 (mid-pack masters)",
     DISTANCES_KM["marathon"], "3:00:00", 40, "M", 2025),

    ("F half-marathon 1:30:00 age 35",
     DISTANCES_KM["hm"], "1:30:00", 35, "F", 2025),

    ("Age interpolation: 75.5yo M 10K @ 50:00",
     DISTANCES_KM["10k"], "50:00", 75.5, "M", 2025),

    ("Distance interpolation: 7.5K (between 6K & 8K) M @ 30:00 age 40",
     7.5, "30:00", 40, "M", 2025),

    ("Out of range: 500m (below shortest) → should be None",
     0.5, "1:30", 30, "M", 2025),

    ("Edge: max tabulated age 100 M road mile 12:00",
     DISTANCES_KM["1mi"], "12:00", 100, "M", 2025),
]


for label, dist, t_str, age, gender, year in CASES:
    t = parse_time(t_str)
    r = age_grade(dist, t, age, gender, year)
    if r is None:
        print(f"{label}\n  → None (out of range / invalid)\n")
        continue
    print(f"{label}")
    print(f"  factor       = {r.factor:.4f}")
    print(f"  standard     = {format_time(r.standard_sec)} ({r.standard_sec:.2f}s)")
    print(f"  age standard = {format_time(r.age_standard_sec)} ({r.age_standard_sec:.2f}s)")
    print(f"  age-graded   = {format_time(r.age_graded_sec)}")
    print(f"  AP%          = {r.ap_pct:.2f}%")
    print()
