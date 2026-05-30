"""
For the 2025 Main Street Mile only: compute the delta between the AP% as
scored in the CSV (using pre-July-2025 M 1-Mile factors) and the AP% the
current MLDR-2025 calculator gives. Then re-rank the 2025 GP Individual
and Age-Group awards with the corrected Main Street Mile scores and show
who moved.
"""

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mldr import age_grade

CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "gp-scores", "2025MAUSATF", "All-Table 1.csv"
)
MILE_NAME = "Main Street Mile"
MILE_KM = 1.609344

# Same mapping as the explorer; only used to verify other rows are unchanged.
RACE_DIST_KM = {
    "Adrenaline 5k": 5.0, "Main Line 5k": 5.0, "Main Street Mile": 1.609344,
    "Frostbite 5 Mile": 8.04672, "Revolutionary 5 Miler": 8.04672,
    "Red Rose 5 Miler": 8.04672, "Scott Coffee": 8.04672,
    "Rothmans 8k": 8.0, "Ben Franklin Bridge 10k": 10.0,
    "Delaware Distance Classic": 15.0, "Broad Street": 16.09344,
    "PDR": 21.0975, "Philly Half": 21.0975, "Philly Marathon": 42.195,
}


# ── Load + compute corrected AP% for Main Street Mile ────────────────────────
def load():
    rows = []
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            try:
                h = int(row["HH"]); m = int(row["MM"]); s = int(row["SS"])
                t = h * 3600 + m * 60 + s
                age = int(row["AGE"]); g = row["G"].strip()
                csv_ap = float(row["AP%"])
            except (KeyError, ValueError):
                continue
            race = row["Race"].strip()
            name = (row["First Name"] + " " + row["Last Name"]).strip()
            club = row["Club"].strip()
            if t <= 0 or race not in RACE_DIST_KM:
                continue
            calc_ap = csv_ap
            if race == MILE_NAME:
                r = age_grade(MILE_KM, t, age, g, year=2025)
                if r is not None:
                    calc_ap = round(r.ap_pct, 3)
            rows.append({
                "name": name, "club": club, "age": age, "gender": g,
                "race": race, "time_sec": t,
                "csv_ap": csv_ap, "calc_ap": calc_ap,
            })
    return rows


# ── Awards ────────────────────────────────────────────────────────────────────
def age_group(age):
    if age < 15: return "U15"
    if age >= 100: return "100+"
    lo = ((age - 15) // 5) * 5 + 15
    return f"{lo}-{lo+4}"


def gp_age_by_runner(rows):
    """Per-runner age = min(age) across that runner's 2025 races (≈ age at first race)."""
    a = {}
    for r in rows:
        k = (r["name"], r["gender"])
        if k not in a or r["age"] < a[k]:
            a[k] = r["age"]
    return a


def individual_standings(rows, ap_field):
    """Best-6 AP% sum, by gender, returned sorted desc."""
    byrunner = defaultdict(list)
    clubs = {}
    ages = gp_age_by_runner(rows)
    for r in rows:
        k = (r["name"], r["gender"])
        byrunner[k].append(r[ap_field])
        clubs[k] = r["club"]
    out = {"M": [], "F": []}
    for (name, g), aps in byrunner.items():
        aps.sort(reverse=True)
        out[g].append({
            "name": name, "club": clubs[(name, g)],
            "age": ages[(name, g)],
            "n": len(aps),
            "total": round(sum(aps[:6]), 3),
        })
    for g in out:
        out[g].sort(key=lambda x: -x["total"])
    return out


def age_group_standings(rows, ap_field):
    """5/3/1 per (race, gender, group). Eligibility ≥3 races. Returns
    {gender: {group: [ranked runners with points]}}.
    """
    ages = gp_age_by_runner(rows)
    races_per = defaultdict(set)
    for r in rows:
        races_per[(r["name"], r["gender"])].add(r["race"])

    points = defaultdict(lambda: {"name": None, "club": None, "group": None,
                                  "gp_age": None, "gender": None,
                                  "total": 0, "breakdown": []})
    PTS = [5, 3, 1]
    races = sorted({r["race"] for r in rows})
    for race in races:
        for gender in ("M", "F"):
            inrace = [r for r in rows if r["race"] == race and r["gender"] == gender]
            by_grp = defaultdict(list)
            for r in inrace:
                k = (r["name"], r["gender"])
                by_grp[age_group(ages[k])].append(r)
            for grp, runners in by_grp.items():
                runners.sort(key=lambda r: -r[ap_field])
                for i, r in enumerate(runners[:3]):
                    k = (r["name"], r["gender"])
                    entry = points[k]
                    entry["name"] = r["name"]; entry["club"] = r["club"]
                    entry["gender"] = gender; entry["gp_age"] = ages[k]
                    entry["group"] = grp
                    entry["total"] += PTS[i]
                    entry["breakdown"].append((race, i + 1, PTS[i]))

    out = {"M": defaultdict(list), "F": defaultdict(list)}
    for k, e in points.items():
        e["n_races"] = len(races_per[k])
        e["eligible"] = e["n_races"] >= 3
        out[e["gender"]][e["group"]].append(e)
    for g in out:
        for grp in out[g]:
            out[g][grp].sort(key=lambda x: (-x["total"], x["name"]))
    return out


# ── Reporting ────────────────────────────────────────────────────────────────
def print_mile_delta(rows):
    mile = [r for r in rows if r["race"] == MILE_NAME and r["calc_ap"] != r["csv_ap"]]
    mile.sort(key=lambda r: r["calc_ap"] - r["csv_ap"])
    print(f"\n=== Per-runner delta on Main Street Mile (n={len(mile)}) ===")
    print(f"{'Name':<26} {'G':<2} {'Age':>3} {'Time':>6} {'CSV AP%':>8} {'Calc AP%':>9} {'Δ':>7}")
    print("-" * 70)
    for r in mile:
        delta = r["calc_ap"] - r["csv_ap"]
        mm = r["time_sec"] // 60; ss = r["time_sec"] % 60
        print(f"{r['name']:<26} {r['gender']:<2} {r['age']:>3} "
              f"{mm:>3d}:{ss:02d} {r['csv_ap']:>8.3f} {r['calc_ap']:>9.3f} {delta:>+7.3f}")
    bumps_up = sum(1 for r in mile if r["calc_ap"] > r["csv_ap"])
    bumps_dn = sum(1 for r in mile if r["calc_ap"] < r["csv_ap"])
    print(f"\nSummary: {bumps_up} runners would score higher under new table, "
          f"{bumps_dn} lower. Max ↑ {max(r['calc_ap']-r['csv_ap'] for r in mile):+.3f}, "
          f"max ↓ {min(r['calc_ap']-r['csv_ap'] for r in mile):+.3f}.")


def diff_individual(rows):
    before = individual_standings(rows, "csv_ap")
    after  = individual_standings(rows, "calc_ap")
    print("\n=== Individual standings (top 10 — Best 6 AP%) ===")
    for gender in ("M", "F"):
        b_idx = {r["name"]: (i + 1, r["total"]) for i, r in enumerate(before[gender])}
        a_idx = {r["name"]: (i + 1, r["total"]) for i, r in enumerate(after[gender])}
        print(f"\n--- {'Men' if gender == 'M' else 'Women'} ---")
        print(f"{'Rk':>3} {'Name':<26} {'CSV Total':>10} {'New Total':>10} "
              f"{'ΔTotal':>7} {'Old Rk':>7} {'ΔRk':>5}")
        print("-" * 75)
        for i, r in enumerate(after[gender][:10]):
            new_rk = i + 1
            old_rk, old_tot = b_idx.get(r["name"], (None, None))
            d_rk = (old_rk - new_rk) if old_rk else "new"
            d_tot = r["total"] - old_tot if old_tot is not None else None
            d_tot_s = f"{d_tot:+.3f}" if d_tot is not None else "  N/A "
            d_rk_s = f"{d_rk:+d}" if isinstance(d_rk, int) else d_rk
            old_rk_s = str(old_rk) if old_rk else "—"
            print(f"{new_rk:>3} {r['name']:<26} {old_tot if old_tot is not None else 0:>10.3f} "
                  f"{r['total']:>10.3f} {d_tot_s:>7} {old_rk_s:>7} {d_rk_s:>5}")
        # Also show anyone in old top 10 who dropped out
        dropped = [n for n in b_idx if b_idx[n][0] <= 10 and a_idx.get(n, (99, 0))[0] > 10]
        if dropped:
            print(f"\n  Dropped out of top 10: {', '.join(dropped)}")


def diff_age_group(rows):
    before = age_group_standings(rows, "csv_ap")
    after  = age_group_standings(rows, "calc_ap")
    print("\n=== Age-group podium changes ===")
    print("(Only groups where the order of the top 3 — or who is eligible — changes.)\n")
    any_change = False
    for gender in ("M", "F"):
        groups = sorted(set(list(before[gender].keys()) + list(after[gender].keys())),
                        key=lambda g: int(g.split("-")[0]) if "-" in g else 999)
        for grp in groups:
            b = before[gender].get(grp, [])
            a = after[gender].get(grp, [])
            # Compare order of eligible runners only (ineligible can't earn the award).
            def podium_names(lst):
                return tuple(e["name"] for e in lst[:3] if e["eligible"])
            if podium_names(b) == podium_names(a):
                continue
            any_change = True
            print(f"  {'Men' if gender == 'M' else 'Women'} {grp}:")
            print(f"    Before: {[(e['name'], e['total']) for e in b[:3] if e['eligible']]}")
            print(f"    After : {[(e['name'], e['total']) for e in a[:3] if e['eligible']]}")
    if not any_change:
        print("  (No order changes — only point totals shifted within unchanged podiums.)")

    # Also show point-only deltas (for completeness).
    # Note: women's F 1-mile factors were NOT revised in July 2025, so no
    # women have an AP% delta even though many ran the Mile.
    print("\n=== Age-group point-total shifts (Men only — F 1-mile factors unchanged) ===")
    shifts = []
    for gender in ("M", "F"):
        for grp in before[gender]:
            bmap = {e["name"]: e["total"] for e in before[gender][grp]}
            amap = {e["name"]: e["total"] for e in after[gender].get(grp, [])}
            for name in bmap:
                d = amap.get(name, 0) - bmap[name]
                if d != 0:
                    shifts.append((gender, grp, name, bmap[name], amap.get(name, 0), d))
    if not shifts:
        print("  (none)")
    else:
        shifts.sort(key=lambda x: -abs(x[5]))
        print(f"  {'G':<2} {'Group':<6} {'Name':<26} {'Old':>4} {'New':>4} {'Δ':>4}")
        for g, grp, n, ob, na, d in shifts[:25]:
            print(f"  {g:<2} {grp:<6} {n:<26} {ob:>4} {na:>4} {d:>+4}")


def main():
    rows = load()
    print(f"Loaded {len(rows)} performances from 2025 GP")
    print_mile_delta(rows)
    diff_individual(rows)
    diff_age_group(rows)


if __name__ == "__main__":
    main()
