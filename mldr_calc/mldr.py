"""
Python port of the MLDR/WMA road age-grading calculator.

Source: https://www.howardgrubb.co.uk/athletics/mldrroad25.html
Author of original JS: Howard Grubb, 1999-2025.

The interpolation logic (bilinear over distance × age) mirrors the JS
`setMileage`, `setAge`, and `lookup_factor` functions exactly. Behaviour
at table edges intentionally matches the JS:
  - Out of distance range  → no result (returns None).
  - Out of age range       → clamps to nearest tabulated age.
  - Exact distance match   → no interpolation; uses that row's standard.

AP% = 100 * standard / (actual_time * age_factor)
    = 100 * age_standard / actual_time
"""

from typing import Optional
from dataclasses import dataclass

from factors import FACTOR_SETS


# Which factor set to use, keyed by (gender, year).
SET_FOR = {
    ("M", 2025): "MLDR_25_M_facs",
    ("F", 2025): "MLDR_25_F_facs",
    ("M", 2020): "MLDR_20_M_facs",
    ("F", 2020): "MLDR_20_F_facs",
    ("M", 2015): "WMA_15_M_facs",
    ("F", 2015): "WMA_15_F_facs",
    ("M", 2010): "WMA_10_M_facs",
    ("F", 2010): "WMA_10_F_facs",
}


@dataclass
class AgeGradeResult:
    factor: float               # interpolated age factor (≤ 1)
    standard_sec: float         # interpolated open-age standard time (s)
    age_standard_sec: float     # standard / factor (= age-adjusted target time)
    age_graded_sec: float       # actual_time * factor (= open-age equivalent)
    ap_pct: float               # age-performance percentage


def _find_distance_indices(events, dist_km):
    """Mirror JS setMileage(): return (ifac, ifac1, pfac).

    Bracket the chosen distance between two events; pfac is the fractional
    position. Returns (-1 or nfac, ..., 0) when out of range.
    """
    nfac = len(events)
    i = -1
    while True:
        cond1 = i < nfac - 1 and events[i + 1]["distance_km"] <= dist_km
        cond2 = i == nfac - 1 and events[i]["distance_km"] < dist_km
        if cond1 or cond2:
            i += 1
        else:
            break

    ifac = i
    if 0 <= i < nfac - 1:
        ifac1 = i + 1
    else:
        ifac1 = i

    pfac = 0.0
    if ifac >= 0 and ifac1 < nfac and ifac != ifac1:
        pfac = (dist_km - events[ifac]["distance_km"]) / (
            events[ifac1]["distance_km"] - events[ifac]["distance_km"]
        )
    return ifac, ifac1, pfac


def _find_age_indices(ages, age):
    """Mirror JS setAge(): return (iage, iage1, page).

    Bracket the chosen age between two tabulated ages. Clamps to the
    youngest or oldest entry when out of range.
    """
    nage = len(ages)
    iage = -1
    iage1 = 0
    i = 0
    while i < nage and ages[i] < age:
        i += 1

    if i == 0:
        iage = 0
        iage1 = 0
    if i >= nage - 1:
        iage = nage - 1
        iage1 = nage - 1
    if 0 < i < nage - 1:
        iage = i - 1
        iage1 = i

    page = 0.0
    if ages[iage] != age and iage != iage1:
        page = (age - ages[iage]) / (ages[iage1] - ages[iage])
    return iage, iage1, page


def _interpolate(events, ages, dist_km, age):
    """Return (factor, standard_sec) or None if distance is out of range."""
    ifac, ifac1, pfac = _find_distance_indices(events, dist_km)
    iage, iage1, page = _find_age_indices(ages, age)
    nfac = len(events)

    # Same gate as JS lookup_factor()
    if not (iage >= 0 and ifac >= 0 and ifac1 < nfac):
        return None

    f00 = events[ifac]["age_factors"][iage]      # (dist_lo, age_lo)
    f01 = events[ifac]["age_factors"][iage1]     # (dist_lo, age_hi)
    f10 = events[ifac1]["age_factors"][iage]     # (dist_hi, age_lo)
    f11 = events[ifac1]["age_factors"][iage1]    # (dist_hi, age_hi)

    factor = (
        (1.0 - pfac) * (page * f01 + (1.0 - page) * f00)
        + pfac * (page * f11 + (1.0 - page) * f10)
    )
    standard = (1.0 - pfac) * events[ifac]["standard_sec"] + pfac * events[ifac1]["standard_sec"]
    return factor, standard


def age_grade(
    distance_km: float,
    time_sec: float,
    age: float,
    gender: str,
    year: int = 2025,
) -> Optional[AgeGradeResult]:
    """Compute age-graded result for a road performance.

    Args:
        distance_km: race distance in kilometres.
        time_sec:    finish time in seconds.
        age:         athlete age (float allowed for interpolation).
        gender:      'M' or 'F'.
        year:        which table to use: 2025 (default), 2020, 2015, or 2010.

    Returns None if the distance is outside the table or if inputs are invalid.
    """
    if time_sec <= 0:
        return None
    key = (gender, year)
    if key not in SET_FOR:
        raise ValueError(f"No factor set for gender={gender!r}, year={year}")
    table = FACTOR_SETS[SET_FOR[key]]

    res = _interpolate(table["events"], table["ages"], distance_km, age)
    if res is None:
        return None
    factor, standard = res
    if factor <= 0:
        return None

    age_graded = time_sec * factor
    age_standard = standard / factor
    ap_pct = 100.0 * age_standard / time_sec
    return AgeGradeResult(
        factor=factor,
        standard_sec=standard,
        age_standard_sec=age_standard,
        age_graded_sec=age_graded,
        ap_pct=ap_pct,
    )


# Distance helpers for common road events (kilometres).
DISTANCES_KM = {
    "1mi": 1.609344,
    "5k":  5.0,
    "6k":  6.0,
    "4mi": 6.437376,
    "8k":  8.0,
    "5mi": 8.04672,
    "10k": 10.0,
    "7mi": 11.265408,
    "12k": 12.0,
    "15k": 15.0,
    "10mi": 16.09344,
    "20k": 20.0,
    "hm":  21.0975,
    "25k": 25.0,
    "30k": 30.0,
    "marathon": 42.195,
    "50k": 50.0,
    "50mi": 80.4672,
    "100k": 100.0,
    "100mi": 160.9344,
    "150k": 150.0,
    "200km": 200.0,
}


def parse_time(s: str) -> float:
    """Convert 'HH:MM:SS' / 'MM:SS' / 'SS' to seconds (float)."""
    parts = s.strip().split(":")
    nums = [float(p) for p in parts]
    if len(nums) == 1: return nums[0]
    if len(nums) == 2: return nums[0] * 60 + nums[1]
    if len(nums) == 3: return nums[0] * 3600 + nums[1] * 60 + nums[2]
    raise ValueError(f"Bad time format: {s!r}")


def format_time(sec: float) -> str:
    """Inverse of parse_time, for printing."""
    sec = round(sec, 1)
    h = int(sec // 3600); sec -= h * 3600
    m = int(sec // 60);   sec -= m * 60
    if h: return f"{h}:{m:02d}:{sec:04.1f}"
    if m: return f"{m}:{sec:04.1f}"
    return f"{sec:.2f}"


if __name__ == "__main__":
    # Quick demo
    r = age_grade(1.609344, 452, 82, "M")
    print(f"82M road mile in 7:32 → factor={r.factor:.4f}, AP%={r.ap_pct:.2f}%")
