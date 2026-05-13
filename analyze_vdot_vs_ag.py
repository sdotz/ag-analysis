"""
Analyze discrepancies between VDOT score and Age Grade percentage across
distances and genders.

VDOT: Jack Daniels' measure of raw aerobic capacity (higher = faster runner).
AG%:  Fraction of the age-group world standard the performance represents
      (higher = better relative to peers of the same age/gender).

Key question: do they *rank* performances the same way, and where do they diverge?

We use within-group percentile ranks (0–100) so both metrics are on the same
scale and the comparison is not distorted by outliers or absolute range.
delta = pct_rank(AG%) − pct_rank(VDOT)
  > 0  → AG rewards this performance more than VDOT does
  < 0  → VDOT rewards this performance more than AG does
"""

import math
import os
import pandas as pd
import numpy as np
try:
    from scipy import stats as _scipy_stats
    def spearmanr(a, b):
        return _scipy_spearmanr(a, b)
except ImportError:
    # Fallback: Pearson on ranks (equivalent to Spearman)
    def spearmanr(a, b):
        a_arr = np.array(a)
        b_arr = np.array(b)
        n = len(a_arr)
        a_rank = a_arr.argsort().argsort()
        b_rank = b_arr.argsort().argsort()
        r = np.corrcoef(a_rank, b_rank)[0, 1]
        # approximate p-value
        t = r * math.sqrt((n - 2) / (1 - r**2 + 1e-15))
        from math import erfc, sqrt
        pval = erfc(abs(t) / sqrt(2))
        return r, pval
from age_grade import AgeGradeCalculator

DISTANCE_METERS = {
    "Mile":     1609.344,
    "5K":       5000.0,
    "8k":       8000.0,
    "8K":       8000.0,
    "10K":     10000.0,
    "12K":     12000.0,
    "15K":     15000.0,
    "10 Mile": 16093.44,
    "20K":     20000.0,
    "25K":     25000.0,
    "30K":     30000.0,
    "H Mar":   21097.5,
    "Marathon":42195.0,
}

DIRS = {
    "M": "msab/men",
    "F": "msab/women",
}

# Plausible VDOT range — filter obvious data errors
VDOT_MIN, VDOT_MAX = 10, 100
# AG% ceiling for record-breaking performances allowed to exceed 100%
AG_MAX = 125


def vdot_from_race(distance_m: float, time_sec: float) -> float:
    t = time_sec / 60.0
    v = distance_m / t
    vo2     = -4.60 + 0.182258 * v + 0.000104 * v ** 2
    pct_max = (0.8
               + 0.1894393 * math.exp(-0.012778  * t)
               + 0.2989558 * math.exp(-0.1932605 * t))
    return vo2 / pct_max


def extract_distance_key(filename: str) -> str:
    return filename.replace("-Table 1.csv", "").strip()


def load_all_data(ag_calc: AgeGradeCalculator) -> pd.DataFrame:
    rows = []
    for gender_code, directory in DIRS.items():
        if not os.path.isdir(directory):
            print(f"  Warning: directory not found: {directory}")
            continue
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".csv"):
                continue
            dist_key = extract_distance_key(fname)
            dist_m = DISTANCE_METERS.get(dist_key)
            if dist_m is None:
                print(f"  Warning: no distance for '{dist_key}' — skipping")
                continue

            df = pd.read_csv(os.path.join(directory, fname))
            for _, row in df.iterrows():
                time_sec = row.get("TIME_SEC")
                age_raw  = row.get("Age")
                if pd.isna(time_sec) or pd.isna(age_raw) or time_sec <= 0:
                    continue
                age = int(age_raw)
                if age <= 0:
                    continue

                vdot = vdot_from_race(dist_m, float(time_sec))
                if not (VDOT_MIN <= vdot <= VDOT_MAX):
                    continue

                ag_result = ag_calc.result(dist_m, float(time_sec), age, gender_code)
                if ag_result is None:
                    continue
                if not (0 < ag_result.percentage <= AG_MAX):
                    continue

                rows.append({
                    "gender":    gender_code,
                    "distance":  dist_key,
                    "age":       age,
                    "time_sec":  float(time_sec),
                    "vdot":      round(vdot, 2),
                    "ag_pct":    round(ag_result.percentage, 2),
                })

    return pd.DataFrame(rows)


def add_percentile_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """Add within-(gender, distance) percentile ranks for both metrics."""
    df = df.copy()
    df["vdot_rank"]  = df.groupby(["gender", "distance"])["vdot"].rank(pct=True) * 100
    df["ag_rank"]    = df.groupby(["gender", "distance"])["ag_pct"].rank(pct=True) * 100
    df["delta_rank"] = df["ag_rank"] - df["vdot_rank"]
    return df


def sep(title: str = ""):
    width = 72
    if title:
        print(f"\n{'─' * 4} {title} {'─' * max(0, width - len(title) - 6)}")
    else:
        print("─" * width)


def main():
    ag_calc = AgeGradeCalculator()

    print("Loading performances …")
    df = load_all_data(ag_calc)
    counts = df["gender"].value_counts().to_dict()
    print(f"  {len(df):,} valid performances  (M={counts.get('M',0)}, F={counts.get('F',0)})\n")

    df = add_percentile_ranks(df)

    # ── 1. Overall correlation ────────────────────────────────────────────────
    sep("Overall  —  Spearman ρ(AG% rank, VDOT rank)")
    rho, pval = spearmanr(df["ag_rank"], df["vdot_rank"])
    print(f"  ρ = {rho:.3f}  (p ≈ {pval:.2e})")
    print(f"  Mean |rank delta| = {df['delta_rank'].abs().mean():.1f} percentile points")

    # ── 2. By gender ──────────────────────────────────────────────────────────
    sep("By gender")
    for gender, gdf in df.groupby("gender"):
        rho, _ = spearmanr(gdf["ag_rank"], gdf["vdot_rank"])
        label = "Male" if gender == "M" else "Female"
        bias = gdf["delta_rank"].mean()
        print(f"  {label:7s}  n={len(gdf):4d}  ρ={rho:.3f}  "
              f"mean_delta={bias:+.1f}  "
              f"mean |delta|={gdf['delta_rank'].abs().mean():.1f}")

    # ── 3. By distance ────────────────────────────────────────────────────────
    sep("By distance  (mean_delta = AG_rank − VDOT_rank, sorted by |mean_delta|)")
    rows = []
    for (gender, dist), gdf in df.groupby(["gender", "distance"]):
        if len(gdf) < 5:
            continue
        rho, _ = spearmanr(gdf["ag_rank"], gdf["vdot_rank"])
        rows.append({
            "G":          gender,
            "Distance":   dist,
            "n":          len(gdf),
            "mean_AG%":   gdf["ag_pct"].mean(),
            "mean_VDOT":  gdf["vdot"].mean(),
            "mean_Δrank": gdf["delta_rank"].mean(),
            "std_Δrank":  gdf["delta_rank"].std(),
            "ρ":          rho,
        })
    dist_df = (pd.DataFrame(rows)
                 .sort_values("mean_Δrank", key=abs, ascending=False))
    print(dist_df.to_string(index=False, float_format=lambda x: f"{x:+.1f}" if abs(x) < 50 else f"{x:.1f}"))

    # ── 4. Age-band breakdown ─────────────────────────────────────────────────
    sep("By age band  (mean rank delta = AG_rank − VDOT_rank)")
    bins   = [0, 9, 14, 19, 29, 39, 49, 59, 69, 79, 200]
    labels = ["≤9","10-14","15-19","20-29","30-39","40-49","50-59","60-69","70-79","80+"]
    df["age_band"] = pd.cut(df["age"], bins=bins, labels=labels)

    age_tbl = (df.groupby(["gender", "age_band"], observed=True)["delta_rank"]
                 .agg(n="count", mean_delta="mean", std_delta="std")
                 .reset_index())
    print(age_tbl.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    print()
    print("  Interpretation: positive delta → AG rewards this age group more than VDOT.")
    print("  Expected: large positive delta for very young and very old athletes")
    print("  (AG factors adjust for age; VDOT sees only raw speed).")

    # ── 5. Biggest individual discrepancies ───────────────────────────────────
    sep("Top 12 where AG ranks much higher than VDOT  (AG over-rewards)")
    cols = ["gender","distance","age","time_sec","vdot","ag_pct","delta_rank"]
    print(df.nlargest(12, "delta_rank")[cols].to_string(index=False))

    sep("Top 12 where VDOT ranks much higher than AG  (VDOT over-rewards)")
    print(df.nsmallest(12, "delta_rank")[cols].to_string(index=False))


if __name__ == "__main__":
    main()
