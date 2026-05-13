#!/usr/bin/env python3
"""
Rebuild the const RAW = {...} data block embedded in index.html.

Adds to every performance record:
  - age_factor  (WMA age factor, 0–1, lower = older runner slower)
  - hdcp_sec    (actual_time - age_graded_mark = time "given" by age grading)

Also adds a top-level 'age_factors' key for the Handicap by Age reference card:
  { gender: { distance_label: { age: factor, ... }, ... }, ... }
  covering ages 5–99 for each distance/gender available.
"""

import json
import math
import os
import re
import sys

import pandas as pd
import numpy as np

from age_grade import AgeGradeCalculator
from analyze_vdot_vs_ag import (
    DISTANCE_METERS,
    DIRS,
    VDOT_MIN, VDOT_MAX, AG_MAX,
    vdot_from_race,
    extract_distance_key,
    add_percentile_ranks,
)

# ── Spearman (no scipy dependency) ──────────────────────────────────────────

def spearman(a, b):
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    a_rank = a_arr.argsort().argsort().astype(float)
    b_rank = b_arr.argsort().argsort().astype(float)
    r = float(np.corrcoef(a_rank, b_rank)[0, 1])
    n = len(a_arr)
    t = r * math.sqrt(max(n - 2, 1) / max(1 - r**2, 1e-15))
    from math import erfc, sqrt
    pval = float(erfc(abs(t) / sqrt(2)))
    return r, pval


# ── Load performances ────────────────────────────────────────────────────────

def load_all_data(ag_calc):
    """Load all MSAB performances; include age_factor and hdcp_sec."""
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

                hdcp_sec = float(time_sec) - ag_result.age_graded_mark_sec

                # Athlete name
                fname_str = str(row.get("First", row.get("Fname", row.get("fname", "")))).strip()
                lname_str = str(row.get("Last",  row.get("Lname", row.get("lname", "")))).strip()
                if fname_str == "nan": fname_str = ""
                if lname_str == "nan": lname_str = ""

                # Time formatted
                ts = int(float(time_sec))
                h, rem = divmod(ts, 3600)
                m_, s = divmod(rem, 60)
                time_fmt = f"{h}:{m_:02d}:{s:02d}" if h else f"{m_}:{s:02d}"

                rows.append({
                    "gender":     gender_code,
                    "distance":   dist_key,
                    "age":        age,
                    "time_sec":   float(time_sec),
                    "vdot":       round(vdot, 2),
                    "ag_pct":     round(ag_result.percentage, 2),
                    "age_factor": round(ag_result.factor, 4),
                    "hdcp_sec":   round(hdcp_sec, 1),
                    "fname":      fname_str,
                    "lname":      lname_str,
                    "time_fmt":   time_fmt,
                })

    df = pd.DataFrame(rows)
    return df


# ── Build age factor lookup table ────────────────────────────────────────────

def build_age_factors(ag_calc):
    """
    Returns { gender: { dist_label: { age: factor } } }
    for every distance/gender available in the WMA tables, ages 5–99.
    """
    result = {"M": {}, "F": {}}
    ref_time = 3600.0  # 1 hour — arbitrary; factor doesn't depend on time

    for dist_key, dist_m in DISTANCE_METERS.items():
        for gender in ("M", "F"):
            factors_by_age = {}
            for age in range(5, 100):
                r = ag_calc.result(dist_m, ref_time, age, gender)
                if r is not None:
                    factors_by_age[age] = round(r.factor, 4)
            if factors_by_age:
                result[gender][dist_key] = factors_by_age

    return result


# ── Build summary stats (mirrors analyze_vdot_vs_ag logic) ──────────────────

def build_summary(df):
    counts = df["gender"].value_counts().to_dict()
    rho, _ = spearman(df["ag_rank"], df["vdot_rank"])
    return {
        "n":             int(len(df)),
        "n_male":        int(counts.get("M", 0)),
        "n_female":      int(counts.get("F", 0)),
        "rho":           round(rho, 3),
        "mean_abs_delta": round(float(df["delta_rank"].abs().mean()), 1),
    }


def build_by_gender(df):
    out = []
    for gender, gdf in df.groupby("gender"):
        rho, _ = spearman(gdf["ag_rank"], gdf["vdot_rank"])
        out.append({
            "gender":         gender,
            "n":              int(len(gdf)),
            "rho":            round(rho, 3),
            "mean_delta":     round(float(gdf["delta_rank"].mean()), 1),
            "mean_abs_delta": round(float(gdf["delta_rank"].abs().mean()), 1),
            "mean_vdot":      round(float(gdf["vdot"].mean()), 1),
            "mean_ag":        round(float(gdf["ag_pct"].mean()), 1),
        })
    return out


def build_by_distance(df):
    out = []
    for (gender, dist), gdf in df.groupby(["gender", "distance"]):
        if len(gdf) < 5:
            continue
        rho, _ = spearman(gdf["ag_rank"], gdf["vdot_rank"])
        out.append({
            "gender":     gender,
            "distance":   dist,
            "n":          int(len(gdf)),
            "rho":        round(rho, 3),
            "mean_delta": round(float(gdf["delta_rank"].mean()), 1),
            "std_delta":  round(float(gdf["delta_rank"].std()), 1),
            "mean_vdot":  round(float(gdf["vdot"].mean()), 1),
            "mean_ag":    round(float(gdf["ag_pct"].mean()), 1),
        })
    return out


def build_by_age_band(df):
    bins   = [0, 9, 14, 19, 29, 39, 49, 59, 69, 79, 200]
    labels = ["≤9","10-14","15-19","20-29","30-39","40-49","50-59","60-69","70-79","80+"]
    df2 = df.copy()
    df2["age_band"] = pd.cut(df2["age"], bins=bins, labels=labels)
    out = []
    for (gender, band), gdf in df2.groupby(["gender", "age_band"], observed=True):
        out.append({
            "gender":     gender,
            "age_band":   str(band),
            "n":          int(len(gdf)),
            "mean_delta": round(float(gdf["delta_rank"].mean()), 1),
            "std_delta":  round(float(gdf["delta_rank"].std()), 1),
        })
    return out


def build_performances(df):
    records = []
    for _, row in df.iterrows():
        records.append({
            "gender":     row["gender"],
            "distance":   row["distance"],
            "age":        int(row["age"]),
            "time_sec":   row["time_sec"],
            "vdot":       row["vdot"],
            "ag_pct":     row["ag_pct"],
            "age_factor": row["age_factor"],
            "hdcp_sec":   row["hdcp_sec"],
            "delta_rank": round(float(row["delta_rank"]), 1),
            "fname":      row["fname"],
            "lname":      row["lname"],
            "time_fmt":   row["time_fmt"],
        })
    return records


# ── Inject into HTML ─────────────────────────────────────────────────────────

def inject_into_html(raw_obj, html_path="index.html"):
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    new_json = json.dumps(raw_obj, separators=(",", ":"), ensure_ascii=False)
    new_block = f"const RAW = {new_json};"

    # Replace the existing const RAW = {...}; block (greedy across newlines)
    pattern = r"const RAW = \{.*?\};"
    replaced, count = re.subn(pattern, new_block, html, count=1, flags=re.DOTALL)
    if count == 0:
        print("ERROR: could not find 'const RAW = {...};' in index.html", file=sys.stderr)
        sys.exit(1)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(replaced)

    print(f"✓ Injected new RAW data into {html_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Initialising AgeGradeCalculator …")
    ag_calc = AgeGradeCalculator()

    print("Loading performances …")
    df = load_all_data(ag_calc)
    counts = df["gender"].value_counts().to_dict()
    print(f"  {len(df):,} performances  (M={counts.get('M',0)}, F={counts.get('F',0)})")

    print("Adding percentile ranks …")
    df = add_percentile_ranks(df)

    print("Building age factor lookup tables …")
    age_factors = build_age_factors(ag_calc)

    raw = {
        "summary":     build_summary(df),
        "by_gender":   build_by_gender(df),
        "by_distance": build_by_distance(df),
        "by_age_band": build_by_age_band(df),
        "age_factors": age_factors,
        "performances": build_performances(df),
    }

    print(f"  summary: {raw['summary']}")
    print(f"  age_factors distances (M): {sorted(raw['age_factors']['M'].keys())}")
    inject_into_html(raw)
    print("Done.")


if __name__ == "__main__":
    main()
