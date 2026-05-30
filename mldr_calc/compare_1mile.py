"""
Compare the M 1-Mile factors across three versions:

  - MLDR 2020             (in age_grade_calc/RunScore-2020 → mldr.js MLDR_20_M_facs)
  - Sheet (Jan-2025 MLDR) (from the Google sheet's "Standards" tab, MOC=232 s)
  - MLDR 2025 (current)   (mldr.js MLDR_25_M_facs, post-July-2025 update, MOC=227 s)

Because the open-class standard differs (Jan-2025 had MOC=232; the others
have MOC=227), the cleanest cross-comparison is the AGE-GRADED STANDARD
TIME (astd) at each age — i.e. the time a runner of that age needs to
score 100%. We also print the factor for each table on its own basis.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factors import FACTOR_SETS


# Sheet "M | age | 1 Mile" column, copied verbatim from the spreadsheet's
# standards tab (gid=1155532368 has age-graded standard times in seconds).
# MOC = 232.000 s on the sheet's basis.
SHEET_MOC_M = 232.000
SHEET_M_MILE_ASTD = {
    5: 321.330, 6: 308.798, 7: 297.741, 8: 287.948, 9: 279.249, 10: 271.504,
    11: 264.599, 12: 258.438, 13: 252.944, 14: 248.049, 15: 243.697, 16: 239.669,
    17: 235.772, 18: 232.932, 19: 232.000, 20: 232.000, 21: 232.000, 22: 232.000,
    23: 232.000, 24: 232.000, 25: 232.000, 26: 232.000, 27: 232.000, 28: 232.000,
    29: 232.000, 30: 232.000, 31: 232.093, 32: 232.349, 33: 232.791, 34: 233.400,
    35: 234.201, 36: 235.199, 37: 236.373, 38: 237.754, 39: 239.323, 40: 241.089,
    41: 243.085, 42: 245.139, 43: 247.229, 44: 249.355, 45: 251.518, 46: 253.718,
    47: 255.958, 48: 258.237, 49: 260.557, 50: 262.919, 51: 265.325, 52: 267.775,
    53: 270.270, 54: 272.813, 55: 275.404, 56: 278.044, 57: 280.736, 58: 283.480,
    59: 286.278, 60: 289.133, 61: 292.044, 62: 295.015, 63: 298.047, 64: 301.142,
    65: 304.302, 66: 307.529, 67: 310.950, 68: 314.747, 69: 318.988, 70: 323.751,
    71: 328.985, 72: 334.825, 73: 341.227, 74: 348.296, 75: 356.156, 76: 364.780,
    77: 374.375, 78: 384.934, 79: 396.649, 80: 409.749, 81: 424.287, 82: 440.646,
    83: 458.952, 84: 479.636, 85: 503.254, 86: 530.165, 87: 561.336, 88: 597.476,
    89: 640.000, 90: 690.887, 91: 752.270, 92: 828.276, 93: 923.935, 94: 1048.351,
    95: 1217.209, 96: 1457.286, 97: 1828.211, 98: 2470.714, 99: 3860.233, 100: 9133.858,
}


def find_mile(facset):
    for ev in facset["events"]:
        if ev["name"] == "1MileRoad":
            return ev
    return None


def fmt_time(sec):
    if sec >= 3600:
        return "—"
    m = int(sec // 60); s = sec - m * 60
    return f"{m}:{s:05.2f}"


def main():
    f20 = find_mile(FACTOR_SETS["MLDR_20_M_facs"])
    f25 = find_mile(FACTOR_SETS["MLDR_25_M_facs"])
    ages = FACTOR_SETS["MLDR_25_M_facs"]["ages"]
    moc_2020 = f20["standard_sec"]
    moc_2025 = f25["standard_sec"]

    print("M 1-Mile Road factors — three table versions")
    print(f"  Open-class standard:  2020 = {moc_2020:.0f} s   "
          f"Sheet = {SHEET_MOC_M:.0f} s   2025 = {moc_2025:.0f} s")
    print()
    print(f"{'Age':>3}  "
          f"{'f_2020':>7} {'f_Sheet':>8} {'f_2025':>7}  "
          f"{'astd_2020':>10} {'astd_Sheet':>11} {'astd_2025':>10}  "
          f"{'Δ S-2025':>9} {'Δ 2025-2020':>11}")
    print("-" * 105)

    for i, age in enumerate(ages):
        fa20 = f20["age_factors"][i]
        fa25 = f25["age_factors"][i]
        astd_sheet = SHEET_M_MILE_ASTD.get(age)
        if astd_sheet is None:
            continue
        astd_2020 = moc_2020 / fa20
        astd_2025 = moc_2025 / fa25
        fa_sheet = SHEET_MOC_M / astd_sheet
        # Δ in astd; what counts is how the age-graded standard time differs.
        d_sheet_2025 = astd_sheet - astd_2025
        d_2025_2020 = astd_2025 - astd_2020
        print(f"{age:>3}  "
              f"{fa20:>7.4f} {fa_sheet:>8.4f} {fa25:>7.4f}  "
              f"{fmt_time(astd_2020):>10} {fmt_time(astd_sheet):>11} "
              f"{fmt_time(astd_2025):>10}  "
              f"{d_sheet_2025:>+9.1f}s {d_2025_2020:>+11.1f}s")


if __name__ == "__main__":
    main()
