#!/usr/bin/env python3
"""
Build the GP explorer page: gp_explorer.html

Embeds all Grand Prix performance data + team scoring analysis.
"""

import json
import os
import pandas as pd

from age_grade import AgeGradeCalculator

RACE_DISTANCES = {
    "ADR 5K": 5000,
    "Revolutionary 5 Miler": 8046.72,
    "Frostbite 5 Miler": 8046.72,
    "Broad Street": 16093.4,
}


def load_data(csv_path):
    df = pd.read_csv(csv_path)
    records = []
    for _, row in df.iterrows():
        records.append({
            "name": f"{row['First Name']} {row['Last Name']}",
            "age": int(row["AGE"]),
            "gender": row["G"],
            "club": row["Club"],
            "race": row["Race"],
            "place": int(row["Place"]),
            "ap_pct": float(row["AP%"]),
            "time_sec": int(row["HH"]) * 3600 + int(row["MM"]) * 60 + int(row["SS"]),
        })
    return records


def compute_team_scores(records):
    """For each (club, race), find the best valid top-5 scorers and compute team score.

    Scoring rule: team of 4-5 must include at least 1 female.
    If the raw top-5 by AP% has no females, we find the best mix
    that satisfies the constraint (drop the lowest male, add the
    highest-scoring female).
    """
    grouped = {}
    for r in records:
        key = (r["club"], r["race"])
        grouped.setdefault(key, []).append(r)

    teams = []
    for (club, race), members in grouped.items():
        if club == "Unattached":
            continue
        by_ap = sorted(members, key=lambda x: -x["ap_pct"])

        # Try to build a valid top-5
        top5 = by_ap[:5]
        n_female = sum(1 for m in top5 if m["gender"] == "F")
        valid = len(top5) < 4 or n_female >= 1

        if not valid:
            # All top-5 are male — try to satisfy the gender rule two ways:
            # 1. Swap in the best available female (from outside top-5)
            females_outside = [m for m in by_ap[5:] if m["gender"] == "F"]
            if females_outside:
                best_female = females_outside[0]  # already sorted by AP%
                new_top5 = top5[:4] + [best_female]
                new_top5.sort(key=lambda x: -x["ap_pct"])
                top5 = new_top5
                n_female = 1
                valid = True
            else:
                # 2. No females available at all — fall back to top-3 males
                #    (1-3 scorers have no gender requirement)
                top5 = by_ap[:3]
                n_female = 0
                valid = len(top5) > 0

        teams.append({
            "club": club,
            "race": race,
            "score": round(sum(m["ap_pct"] for m in top5), 1),
            "n": len(top5),
            "mean_age": round(sum(m["age"] for m in top5) / len(top5), 1),
            "ages": sorted([m["age"] for m in top5]),
            "n_female": n_female,
            "valid": valid,
            "scorers": [
                {
                    "name": m["name"],
                    "age": m["age"],
                    "gender": m["gender"],
                    "ap_pct": round(m["ap_pct"], 1),
                }
                for m in top5
            ],
        })

    return teams


def build_club_summary(records, teams):
    """Aggregate club stats across all races."""
    clubs = {}
    for r in records:
        if r["club"] == "Unattached":
            continue
        clubs.setdefault(r["club"], []).append(r)

    club_stats = []
    for club, members in clubs.items():
        club_teams = [t for t in teams if t["club"] == club and t["valid"]]
        best_score = max((t["score"] for t in club_teams), default=0)
        total_score = sum(t["score"] for t in club_teams)
        n_races = len(club_teams)
        all_ages = [m["age"] for m in members]
        # Scoring members across all races
        scoring_ages = []
        for t in club_teams:
            scoring_ages.extend(t["ages"])
        club_stats.append({
            "club": club,
            "n_members": len(set(m["name"] for m in members)),
            "n_results": len(members),
            "n_races": n_races,
            "mean_age": round(sum(all_ages) / len(all_ages), 1),
            "mean_scoring_age": round(sum(scoring_ages) / len(scoring_ages), 1)
            if scoring_ages
            else None,
            "best_score": best_score,
            "total_score": round(total_score, 1),
            "mean_ap": round(sum(m["ap_pct"] for m in members) / len(members), 1),
            "n_female": sum(1 for m in members if m["gender"] == "F"),
            "n_male": sum(1 for m in members if m["gender"] == "M"),
        })

    club_stats.sort(key=lambda x: -x["total_score"])
    return club_stats


def add_youth35_scores(records, ag_calc):
    """Add ap_pct_35: what each runner's AP% would be if scored at age 35."""
    for r in records:
        if r["age"] <= 35:
            r["ap_pct_35"] = r["ap_pct"]
            continue

        dist_m = RACE_DISTANCES.get(r["race"])
        if dist_m is None:
            r["ap_pct_35"] = r["ap_pct"]
            continue

        # Get factor at actual age and at age 35
        res_actual = ag_calc.result(dist_m, float(r["time_sec"]), r["age"], r["gender"])
        res_35 = ag_calc.result(dist_m, float(r["time_sec"]), 35, r["gender"])

        if res_actual is None or res_35 is None or res_35.factor <= 0:
            r["ap_pct_35"] = r["ap_pct"]
            continue

        # AP%_35 = AP% * factor(actual_age) / factor(35)
        r["ap_pct_35"] = round(r["ap_pct"] * res_actual.factor / res_35.factor, 1)


def main():
    csv_path = "gp-scores/2026MAUSATF/All Races-Table 1.csv"
    print("Loading GP data …")
    records = load_data(csv_path)
    print(f"  {len(records)} results across {len(set(r['race'] for r in records))} races")

    print("Computing youth-35 adjusted scores …")
    ag_calc = AgeGradeCalculator()
    add_youth35_scores(records, ag_calc)
    n_adjusted = sum(1 for r in records if r["ap_pct_35"] != r["ap_pct"])
    print(f"  {n_adjusted} runners adjusted (age > 35)")

    print("Computing team scores …")
    teams = compute_team_scores(records)
    print(f"  {len(teams)} team-race entries")

    print("Building club summaries …")
    club_stats = build_club_summary(records, teams)
    print(f"  {len(club_stats)} clubs")

    data = {
        "performances": records,
        "teams": teams,
        "club_stats": club_stats,
    }

    n_races = len(set(r["race"] for r in records))
    data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    html = build_html(data_json, n_races)

    out_path = "gp_explorer.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Wrote {out_path}")


def build_html(data_json, n_races):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>USATF Mid-Atlantic Grand Prix Explorer</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --border: #2e3250; --text: #e2e8f0; --muted: #8892a4;
    --blue: #4e9af1; --pink: #f16b8a; --green: #4ecb85;
    --yellow: #f5c542; --orange: #f18d4e; --purple: #a78bfa;
    --male: #4e9af1; --female: #f16b8a;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; }}
  h1 {{ font-size: 1.5rem; font-weight: 700; }}
  h2 {{ font-size: 1rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: .75rem; }}

  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; }}
  header p {{ color: var(--muted); font-size: .85rem; margin-top: .25rem; }}

  .filter-bar {{ background: var(--surface); border-top: 1px solid var(--border); padding: .6rem 1.5rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; box-shadow: 0 -2px 8px rgba(0,0,0,.4); }}
  .filter-bar label {{ font-size: .8rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }}
  .filter-bar select {{ background: var(--surface2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: .35rem .6rem; font-size: .85rem; cursor: pointer; min-width: 200px; }}
  .filter-bar select:focus {{ outline: none; border-color: var(--blue); }}
  .filter-bar .active-filter {{ font-size: .75rem; color: var(--blue); cursor: pointer; padding: .2rem .5rem; border: 1px solid var(--blue); border-radius: 4px; }}
  .filter-bar .active-filter:hover {{ background: rgba(78,154,241,.15); }}

  main {{ max-width: 1200px; margin: 0 auto; padding: 1.25rem; padding-bottom: 4rem; display: flex; flex-direction: column; gap: 1.25rem; }}

  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.25rem; }}

  .stats-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: .75rem; }}
  .stat-card {{ background: var(--surface2); border-radius: 8px; padding: .75rem 1rem; }}
  .stat-card .val {{ font-size: 1.5rem; font-weight: 700; }}
  .stat-card .lbl {{ font-size: .72rem; color: var(--muted); margin-top: .1rem; text-transform: uppercase; letter-spacing: .05em; }}
  .val-blue {{ color: var(--blue); }} .val-green {{ color: var(--green); }}
  .val-yellow {{ color: var(--yellow); }} .val-pink {{ color: var(--pink); }}

  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }}
  .chart-wrap canvas {{ max-height: 280px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: .8rem; }}
  thead th {{ background: var(--surface2); color: var(--muted); padding: .5rem .65rem; text-align: left; position: sticky; top: 0; white-space: nowrap; cursor: pointer; user-select: none; }}
  thead th:hover {{ color: var(--text); }}
  tbody tr {{ border-bottom: 1px solid var(--border); transition: background .1s; }}
  tbody tr:hover {{ background: var(--surface2); }}
  td {{ padding: .45rem .65rem; white-space: nowrap; }}
  .badge {{ display: inline-block; padding: .1rem .45rem; border-radius: 4px; font-size: .72rem; font-weight: 600; }}
  .badge-M {{ background: rgba(78,154,241,.2); color: var(--male); }}
  .badge-F {{ background: rgba(241,107,138,.2); color: var(--female); }}

  .age-bar {{ display: inline-block; height: 8px; border-radius: 4px; }}

  details.methodology {{ border: 1px solid var(--border); border-radius: 7px; padding: .4rem .8rem; font-size: .78rem; color: var(--muted); margin-top: .55rem; max-width: 900px; }}
  details.methodology summary {{ cursor: pointer; font-weight: 600; color: var(--text); list-style: none; display: flex; align-items: center; gap: .4rem; user-select: none; }}
  details.methodology summary::-webkit-details-marker {{ display: none; }}
  details.methodology summary::before {{ content: '\\25B6'; font-size: .6rem; transition: transform .15s; color: var(--muted); }}
  details[open].methodology summary::before {{ transform: rotate(90deg); }}
  details.methodology ul {{ margin: .5rem 0 .35rem 1rem; line-height: 1.7; }}
  details.methodology li {{ margin: .2rem 0; }}

  .legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: .75rem; color: var(--muted); margin-top: .5rem; }}
  .legend-item {{ display: flex; align-items: center; gap: .3rem; }}
  .legend-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}

  @media (max-width: 900px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<header>
  <h1>USATF Mid-Atlantic Grand Prix Explorer</h1>
  <p>2026 Club Challenge — age-graded scoring analysis across {n_races} races</p>
  <details class="methodology">
    <summary>Scoring rules &amp; methodology</summary>
    <div style="display:flex;flex-direction:column;gap:.8rem;margin:.6rem 0 .4rem">

      <div>
        <div style="font-weight:600;color:var(--text);margin-bottom:.25rem">General rules (all models)</div>
        <ul>
          <li><strong>Team score</strong> = sum of the top 5 individual scores per race. If 4-5 runners score, at least 1 must be female. Teams of 1-3 have no gender requirement.</li>
          <li><strong>Season standing</strong> = best 8 race scores (lowest races dropped).</li>
          <li>If the top 5 by score are all male, the lowest-scoring male is replaced by the highest-scoring female. If no female is available, the team falls back to 3 scorers.</li>
        </ul>
      </div>

      <div>
        <div style="font-weight:600;color:var(--blue);margin-bottom:.25rem">1. Official AP% (current system)</div>
        <ul>
          <li>Each runner's score is their <strong>age-graded percentage (AP%)</strong> from the 2025 WMA tables.</li>
          <li>AP% = age-adjusted world record / actual time. A 75-year-old running 25:00 for 5K can outscore a 30-year-old running 19:00.</li>
          <li><strong>Bias:</strong> Prime-age world records are set by professional athletes (hard ceiling), while masters records are set by the best amateurs (easier ceiling). This makes it systematically easier for older runners to score high AP%, giving masters-heavy teams a structural advantage.</li>
        </ul>
      </div>

      <div>
        <div style="font-weight:600;color:var(--purple);margin-bottom:.25rem">2. Decade Percentile (experimental)</div>
        <ul>
          <li>Each runner is scored by <strong>percentile rank among runners in the same age decade</strong> (e.g., 40-49), gender, and race.</li>
          <li>The fastest runner in a decade group scores 100%; the slowest scores near 0%.</li>
          <li><strong>Rationale:</strong> Normalizes for competitive depth differences across ages. A 70-year-old must beat other 70-somethings to score high, not just clear a world-record bar that few amateurs approach.</li>
          <li><strong>Limitation:</strong> Small decade groups (e.g., only 2 runners aged 70-79 in a race) produce coarse percentiles. Score depends on who else shows up in your decade, not absolute fitness.</li>
        </ul>
      </div>

      <div>
        <div style="font-weight:600;color:var(--yellow);margin-bottom:.25rem">3. Youth Requirement (experimental)</div>
        <ul>
          <li>Teams must field <strong>at least 2 runners under age 35</strong> among their top-5 scorers. An under-35 female can satisfy both the youth and female requirements.</li>
          <li>If the team cannot field 2 under-35 runners, the <strong>youngest over-35 scorers</strong> filling those youth slots have their AP% <strong>recalculated at a baseline age of 35</strong> — their actual finish time is scored against the age-35 standard instead of their real age standard.</li>
          <li><strong>Example:</strong> A 47-year-old with AP% 87.1% might drop to ~80% when scored at age 35. An 86-year-old with AP% 92.7% would drop to ~45.6%, but she would never be penalized because the penalty targets the <em>youngest</em> over-35 runners (closest to the cutoff), not the oldest.</li>
          <li><strong>Rationale:</strong> Incentivizes clubs to recruit and develop younger runners rather than relying entirely on masters depth. The penalty is proportional — runners just over 35 lose little, while the mechanism still allows masters runners to contribute at their full AP%.</li>
        </ul>
      </div>

    </div>
  </details>
</header>
<main>

  <div class="stats-row" id="stat-cards"></div>

  <div class="card">
    <h2>Current Standings <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— best 8 race scores count (top 5 AP% per race, must include 1 female if 4-5 score)</span></h2>
    <div style="overflow-x:auto">
    <table id="standings-table">
      <thead id="standings-thead"></thead>
      <tbody id="standings-tbody"></tbody>
    </table>
    </div>
  </div>

  <div class="charts-grid">
    <div class="card">
      <h2>Age distribution</h2>
      <div class="chart-wrap"><canvas id="age-hist"></canvas></div>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:var(--male)"></div> Male</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--female)"></div> Female</div>
      </div>
    </div>
    <div class="card">
      <h2>Scoring AP% by Age Band <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— total AP% from top-5 scorers</span></h2>
      <div class="chart-wrap"><canvas id="ap-by-age"></canvas></div>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:var(--blue)"></div> Scoring (top 5)</div>
        <div class="legend-item"><div class="legend-dot" style="background:rgba(142,142,142,.4)"></div> Non-scoring</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Age vs Age-Graded Score <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— does older = higher AP%?</span></h2>
    <div class="chart-wrap"><canvas id="scatter" style="max-height:360px"></canvas></div>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:var(--male)"></div> Male</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--female)"></div> Female</div>
    </div>
  </div>

  <div class="card">
    <h2>Team Scores by Club <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— mean age of top-5 scorers shown</span></h2>
    <div class="chart-wrap"><canvas id="club-chart" style="max-height:400px"></canvas></div>
  </div>

  <div class="card">
    <h2>Scoring Roster Age Profile <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— ages of top-5 scorers per club, all races combined</span></h2>
    <div class="chart-wrap"><canvas id="age-profile" style="max-height:300px"></canvas></div>
  </div>

  <div class="card">
    <h2>Club Standings</h2>
    <div style="overflow-x:auto">
    <table id="club-table">
      <thead>
        <tr>
          <th>Rank</th>
          <th>Club</th>
          <th>Total Score</th>
          <th>Best Race</th>
          <th>Races</th>
          <th>Members</th>
          <th>Mean AP%</th>
          <th>Mean Age (all)</th>
          <th>Mean Age (scoring)</th>
          <th>M / F</th>
        </tr>
      </thead>
      <tbody id="club-tbody"></tbody>
    </table>
    </div>
  </div>

  <div class="card">
    <h2>All Results</h2>
    <div style="overflow-x:auto;max-height:500px">
    <table id="all-table">
      <thead>
        <tr>
          <th>Name</th><th>Age</th><th>G</th><th>Club</th><th>Race</th>
          <th>Place</th><th>AP%</th><th id="decile-col-header" style="display:none">Decade Pctile</th>
        </tr>
      </thead>
      <tbody id="all-tbody"></tbody>
    </table>
    </div>
  </div>

  <div class="card" id="experimental-section">
    <h2>Experimental Scoring Models <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— how alternative models change the standings (see methodology above)</span></h2>
    <div>
      <h2>Rank Change <span style="font-weight:400;font-size:.8rem;color:var(--muted)">— official AP% rank vs alternative models</span></h2>
      <div class="chart-wrap"><canvas id="rank-shift" style="max-height:500px"></canvas></div>
    </div>
    <div style="overflow-x:auto;margin-top:1rem">
      <table id="model-comparison-table">
        <thead>
          <tr>
            <th>Club</th>
            <th>AP% Total</th><th>AP% Rank</th>
            <th>Decile Total</th><th>Decile &Delta;</th>
            <th>Youth35 Total</th><th>Youth35 &Delta;</th>
            <th>Mean Scoring Age</th>
          </tr>
        </thead>
        <tbody id="model-comparison-tbody"></tbody>
      </table>
    </div>
  </div>

</main>

<div class="filter-bar">
  <label for="club-filter">Club</label>
  <select id="club-filter"><option value="">All clubs</option></select>
  <span id="clear-filter" class="active-filter" style="display:none">Clear filter</span>
  <span style="margin-left:auto"></span>
  <label for="scoring-mode">Scoring model</label>
  <select id="scoring-mode">
    <option value="ap">Official AP%</option>
    <option value="decile">Decade Percentile</option>
    <option value="youth35">Youth Requirement (2 under-35)</option>
  </select>
</div>

<script>
const DATA = {data_json};

const allPerfs = DATA.performances;
const allTeams = DATA.teams;
const allClubs = DATA.club_stats;

// ── Compute decade percentile scores ────────────────────────────────────────
// For each (race, gender, age_decade), rank runners by time and assign percentile
function computeDecileScores(perfs) {{
  // Group by (race, gender, decade)
  const groups = {{}};
  perfs.forEach((p,i) => {{
    const decade = Math.floor(p.age / 10) * 10;
    const key = `${{p.race}}|${{p.gender}}|${{decade}}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push({{idx: i, time_sec: p.time_sec, ap_pct: p.ap_pct}});
  }});

  const scores = new Float64Array(perfs.length);
  for (const key in groups) {{
    const g = groups[key];
    // Sort by time ascending (faster = better)
    g.sort((a,b) => a.time_sec - b.time_sec);
    const n = g.length;
    g.forEach((entry, rank) => {{
      // Percentile: 100 * (n - rank) / n  (best = 100, worst ≈ 100/n)
      scores[entry.idx] = Math.round(1000 * (n - rank) / n) / 10;
    }});
  }}
  return scores;
}}

const decileScores = computeDecileScores(allPerfs);

// Attach decile score to each performance record
allPerfs.forEach((p,i) => {{ p.decile_pct = decileScores[i]; }});

function getScore(p, mode) {{
  if (mode === 'decile') return p.decile_pct;
  return p.ap_pct;
}}

// ── Recompute teams under a given scoring mode ──────────────────────────────
function recomputeTeams(perfs, mode) {{
  if (mode === 'ap') return allTeams;

  const grouped = {{}};
  perfs.forEach(p => {{
    if (p.club === 'Unattached') return;
    const key = p.club + '|' + p.race;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(p);
  }});

  const teams = [];
  for (const key in grouped) {{
    const members = grouped[key];
    const [club, race] = key.split('|');

    // For youth35 mode, select team by AP% then apply penalty
    const sortMode = mode === 'youth35' ? 'ap' : mode;
    const byScore = [...members].sort((a,b) => getScore(b,sortMode) - getScore(a,sortMode));

    let top5 = byScore.slice(0,5);
    let nFemale = top5.filter(m=>m.gender==='F').length;
    let valid = top5.length < 4 || nFemale >= 1;

    if (!valid) {{
      const femalesOutside = byScore.slice(5).filter(m=>m.gender==='F');
      if (femalesOutside.length > 0) {{
        top5 = [...top5.slice(0,4), femalesOutside[0]].sort((a,b)=>getScore(b,sortMode)-getScore(a,sortMode));
        nFemale = 1;
        valid = true;
      }} else {{
        top5 = byScore.slice(0,3);
        nFemale = 0;
        valid = top5.length > 0;
      }}
    }}

    // Youth35: check under-35 count and apply penalty to youngest over-35
    let scorerDetails;
    if (mode === 'youth35') {{
      const under35 = top5.filter(m => m.age < 35);
      const over35 = top5.filter(m => m.age >= 35).sort((a,b) => a.age - b.age); // youngest first
      const deficit = Math.max(0, 2 - under35.length);
      // Penalise the youngest `deficit` over-35 runners: use ap_pct_35
      const penalised = new Set(over35.slice(0, deficit).map(m => m.name + '|' + m.race));
      scorerDetails = top5.map(m => {{
        const isPenalised = penalised.has(m.name + '|' + m.race);
        const score = isPenalised ? m.ap_pct_35 : m.ap_pct;
        return {{name: m.name, age: m.age, gender: m.gender, ap_pct: Math.round(score*10)/10, penalised: isPenalised}};
      }});
    }} else {{
      scorerDetails = top5.map(m => ({{
        name: m.name, age: m.age, gender: m.gender,
        ap_pct: Math.round(getScore(m,mode)*10)/10,
      }}));
    }}

    const teamScore = Math.round(scorerDetails.reduce((s,m) => s + m.ap_pct, 0) * 10) / 10;

    teams.push({{
      club, race,
      score: teamScore,
      n: top5.length,
      mean_age: Math.round(top5.reduce((s,m) => s+m.age, 0) / top5.length * 10) / 10,
      ages: top5.map(m=>m.age).sort((a,b)=>a-b),
      n_female: nFemale,
      valid,
      scorers: scorerDetails,
    }});
  }}
  return teams;
}}

// ── Recompute club stats from recomputed teams ──────────────────────────────
function recomputeClubStats(perfs, teams, mode) {{
  if (mode === 'ap') return allClubs;
  const scoreMode = mode === 'youth35' ? 'ap' : mode;

  const clubMap = {{}};
  perfs.forEach(p => {{
    if (p.club === 'Unattached') return;
    if (!clubMap[p.club]) clubMap[p.club] = [];
    clubMap[p.club].push(p);
  }});

  const stats = [];
  for (const club in clubMap) {{
    const members = clubMap[club];
    const clubTeams = teams.filter(t=>t.club===club && t.valid);
    const bestScore = clubTeams.length ? Math.max(...clubTeams.map(t=>t.score)) : 0;
    const totalScore = clubTeams.reduce((s,t)=>s+t.score, 0);
    const nRaces = clubTeams.length;
    const allAges = members.map(m=>m.age);
    const scoringAges = clubTeams.flatMap(t=>t.ages);
    stats.push({{
      club,
      n_members: new Set(members.map(m=>m.name)).size,
      n_results: members.length,
      n_races: nRaces,
      mean_age: Math.round(allAges.reduce((s,a)=>s+a,0)/allAges.length*10)/10,
      mean_scoring_age: scoringAges.length ? Math.round(scoringAges.reduce((s,a)=>s+a,0)/scoringAges.length*10)/10 : null,
      best_score: Math.round(bestScore*10)/10,
      total_score: Math.round(totalScore*10)/10,
      mean_ap: Math.round(members.reduce((s,m)=>s+getScore(m,scoreMode),0)/members.length*10)/10,
      n_female: members.filter(m=>m.gender==='F').length,
      n_male: members.filter(m=>m.gender==='M').length,
    }});
  }}
  stats.sort((a,b)=>b.total_score-a.total_score);
  return stats;
}}

// ── Populate club filter dropdown ───────────────────────────────────────────
const clubNames = [...new Set(allPerfs.map(p=>p.club))].sort();
const clubSel = document.getElementById('club-filter');
const clearBtn = document.getElementById('clear-filter');
const scoringSel = document.getElementById('scoring-mode');
clubNames.forEach(c => {{
  const o = document.createElement('option');
  o.value = c; o.textContent = c;
  clubSel.appendChild(o);
}});

let activeClub = '';
let scoringMode = 'ap';
clubSel.addEventListener('change', () => {{ activeClub = clubSel.value; render(); }});
clearBtn.addEventListener('click', () => {{ activeClub = ''; clubSel.value = ''; render(); }});
scoringSel.addEventListener('change', () => {{ scoringMode = scoringSel.value; render(); }});

// ── Helpers ─────────────────────────────────────────────────────────────────
const ageBins = Array.from({{length:17}},(_,i)=>i*5+5);
const ageLabels = ageBins.slice(0,-1).map((b,i)=>`${{b}}-${{ageBins[i+1]-1}}`);
const apBins = Array.from({{length:11}},(_,i)=>i*10);
const apLabels = apBins.slice(0,-1).map((b,i)=>`${{b}}-${{apBins[i+1]-1}}`);
function binCount(arr,bins) {{ return bins.slice(0,-1).map((b,i)=>arr.filter(a=>a>=b&&a<bins[i+1]).length); }}
function trunc(s,n) {{ return s.length>n ? s.slice(0,n-1)+'\\u2026' : s; }}
function ageColor(a) {{
  const t=Math.max(0,Math.min(1,(a-25)/50));
  return `rgba(${{Math.round(78+177*t)}},${{Math.round(154-103*t)}},${{Math.round(241-193*t)}},.75)`;
}}

// ── Chart instances (destroyed on re-render) ────────────────────────────────
let charts = {{}};
function destroyCharts() {{ Object.values(charts).forEach(c=>c.destroy()); charts={{}}; }}

// ── Main render ─────────────────────────────────────────────────────────────
function render() {{
  clearBtn.style.display = activeClub ? 'inline-block' : 'none';

  const useTeamsAll = recomputeTeams(allPerfs, scoringMode);
  const useClubsAll = recomputeClubStats(allPerfs, useTeamsAll, scoringMode);
  const scoreLabel = scoringMode === 'decile' ? 'Decade Pctile' : scoringMode === 'youth35' ? 'AP% (Youth Req.)' : 'AP%';

  const perfs = activeClub ? allPerfs.filter(p=>p.club===activeClub) : allPerfs;
  const teams = activeClub ? useTeamsAll.filter(t=>t.club===activeClub) : useTeamsAll;
  const clubs = activeClub ? useClubsAll.filter(c=>c.club===activeClub) : useClubsAll;

  destroyCharts();

  // ── Stat cards ────────────────────────────────────────────────────────────
  const nResults = perfs.length;
  const nRunners = new Set(perfs.map(p=>p.name)).size;
  const nRaces   = new Set(perfs.map(p=>p.race)).size;
  const nClubs   = clubs.length;
  const meanAge  = nResults ? (perfs.reduce((s,p)=>s+p.age,0)/nResults).toFixed(1) : '—';
  const meanScore = nResults ? (perfs.reduce((s,p)=>s+getScore(p,scoringMode),0)/nResults).toFixed(1)+'%' : '—';

  document.getElementById('stat-cards').innerHTML = [
    ['val-blue',   nResults, 'Total results'],
    ['val-green',  nRunners, 'Unique runners'],
    ['val-yellow', nRaces,   'Races'],
    ['val-pink',   nClubs,   activeClub ? 'Club' : 'Clubs'],
    ['val-blue',   meanAge,  'Mean age'],
    ['val-green',  meanScore, 'Mean '+scoreLabel],
  ].map(([c,v,l])=>`<div class="stat-card"><div class="val ${{c}}">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('');

  // ── Current standings ─────────────────────────────────────────────────────
  // Compute standings with proper best-8 rule
  const allRaceNames = [...new Set(useTeamsAll.map(t=>t.race))];
  const standingsClubs = [...new Set(useTeamsAll.filter(t=>t.valid).map(t=>t.club))];
  const standings = standingsClubs.map(club => {{
    const raceScores = {{}};
    allRaceNames.forEach(race => {{
      const t = useTeamsAll.find(t=>t.club===club && t.race===race && t.valid);
      raceScores[race] = t ? t.score : null;
    }});
    const validScores = Object.values(raceScores).filter(s=>s!==null).sort((a,b)=>b-a);
    const best8 = validScores.slice(0,8);
    const total = best8.reduce((s,v)=>s+v,0);
    const meanScoringAge = (() => {{
      const clubTeams = useTeamsAll.filter(t=>t.club===club && t.valid);
      const ages = clubTeams.flatMap(t=>t.scorers.map(s=>s.age));
      return ages.length ? (ages.reduce((s,a)=>s+a,0)/ages.length).toFixed(1) : '—';
    }})();
    return {{club, raceScores, total: Math.round(total*10)/10, nRaces: validScores.length, meanScoringAge}};
  }}).sort((a,b)=>b.total-a.total);

  // Filter if club selected
  const displayStandings = activeClub ? standings.filter(s=>s.club===activeClub) : standings;

  const sHead = document.getElementById('standings-thead');
  sHead.innerHTML = `<tr>
    <th>Rank</th><th>Club</th>
    ${{allRaceNames.map(r=>`<th style="max-width:120px;overflow:hidden;text-overflow:ellipsis">${{r}}</th>`).join('')}}
    <th>Total</th><th>Races</th><th>Mean Scoring Age</th>
  </tr>`;

  const sTbody = document.getElementById('standings-tbody');
  sTbody.innerHTML = displayStandings.map((s,i) => {{
    const highlight = s.club===activeClub ? 'background:var(--surface2)' : '';
    const raceCells = allRaceNames.map(race => {{
      const sc = s.raceScores[race];
      if(sc===null) return `<td style="color:var(--muted)">\\u2014</td>`;
      return `<td>${{sc.toFixed(1)}}</td>`;
    }}).join('');
    const ageColor = parseFloat(s.meanScoringAge)>50 ? 'var(--orange)' : 'var(--blue)';
    return `<tr style="${{highlight}}">
      <td>${{i+1}}</td>
      <td>${{s.club}}</td>
      ${{raceCells}}
      <td style="font-weight:700;color:var(--green)">${{s.total.toFixed(1)}}</td>
      <td>${{s.nRaces}}</td>
      <td style="color:${{ageColor}}">${{s.meanScoringAge}}</td>
    </tr>`;
  }}).join('');

  // ── Age histogram ─────────────────────────────────────────────────────────
  const mAges = perfs.filter(p=>p.gender==='M').map(p=>p.age);
  const fAges = perfs.filter(p=>p.gender==='F').map(p=>p.age);

  charts.ageHist = new Chart(document.getElementById('age-hist'), {{
    type:'bar',
    data:{{labels:ageLabels,datasets:[
      {{label:'Male',data:binCount(mAges,ageBins),backgroundColor:'rgba(78,154,241,.7)',borderRadius:3}},
      {{label:'Female',data:binCount(fAges,ageBins),backgroundColor:'rgba(241,107,138,.7)',borderRadius:3}},
    ]}},
    options:{{responsive:true,plugins:{{legend:{{display:false}}}},scales:{{
      y:{{title:{{display:true,text:'Count'}}}},
      x:{{title:{{display:true,text:'Age'}},grid:{{display:false}}}}
    }}}}
  }});

  // ── Scoring by age band ────────────────────────────────────────────────────
  const validTeams = activeClub ? useTeamsAll.filter(t=>t.club===activeClub && t.valid) : useTeamsAll.filter(t=>t.valid);
  const scorerEntries = [];
  validTeams.forEach(t => {{
    t.scorers.forEach(s => {{
      scorerEntries.push({{age: s.age, ap: s.ap_pct}});
    }});
  }});

  const ageBandEdges = [0,20,30,40,50,60,70,80,100];
  const ageBandLabels = ['<20','20-29','30-39','40-49','50-59','60-69','70-79','80+'];
  function sumAPByBand(entries) {{
    return ageBandEdges.slice(0,-1).map((lo,i) => {{
      const hi = ageBandEdges[i+1];
      return Math.round(entries.filter(e=>e.age>=lo && e.age<hi).reduce((s,e)=>s+e.ap,0)*10)/10;
    }});
  }}

  const nonScorerEntries = perfs
    .filter(p=>p.club!=='Unattached')
    .map(p=>({{age:p.age, ap:getScore(p,scoringMode)}}));
  const scoringByBand = sumAPByBand(scorerEntries);
  const allByBand = sumAPByBand(nonScorerEntries);
  const nonScoringByBand = allByBand.map((v,i)=>Math.round(Math.max(0,v-scoringByBand[i])*10)/10);

  charts.apByAge = new Chart(document.getElementById('ap-by-age'), {{
    type:'bar',
    data:{{labels:ageBandLabels,datasets:[
      {{label:'Scoring (top 5)',data:scoringByBand,backgroundColor:'rgba(78,154,241,.7)',borderRadius:3}},
      {{label:'Non-scoring',data:nonScoringByBand,backgroundColor:'rgba(142,142,142,.25)',borderRadius:3}},
    ]}},
    options:{{responsive:true,
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{
        afterBody:ctx=>{{
          const i=ctx[0].dataIndex;
          const total=scoringByBand[i]+nonScoringByBand[i];
          const pct=total>0?((scoringByBand[i]/total)*100).toFixed(0):0;
          return `${{pct}}% of band is scoring`;
        }}
      }}}}}},
      scales:{{
        y:{{title:{{display:true,text:'Total AP%',}},stacked:true}},
        x:{{title:{{display:true,text:'Age band'}},grid:{{display:false}},stacked:true}}
      }}
    }}
  }});

  // ── Age vs score scatter ───────────────────────────────────────────────────
  const mPts = perfs.filter(p=>p.gender==='M').map(p=>({{x:p.age,y:getScore(p,scoringMode),_p:p}}));
  const fPts = perfs.filter(p=>p.gender==='F').map(p=>({{x:p.age,y:getScore(p,scoringMode),_p:p}}));

  charts.scatter = new Chart(document.getElementById('scatter'), {{
    type:'scatter',
    data:{{datasets:[
      {{label:'Male',data:mPts,backgroundColor:'rgba(78,154,241,.45)',pointRadius:4,pointHoverRadius:7}},
      {{label:'Female',data:fPts,backgroundColor:'rgba(241,107,138,.45)',pointRadius:4,pointHoverRadius:7}},
    ]}},
    options:{{responsive:true,
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{
        label:ctx=>{{const p=ctx.raw._p; return [`${{p.name}}`,`Age ${{p.age}} | ${{p.gender}} | ${{p.club}}`,`${{scoreLabel}} ${{getScore(p,scoringMode).toFixed(1)}} | AP% ${{p.ap_pct.toFixed(1)}} | Place ${{p.place}} | ${{p.race}}`];}}
      }}}}}},
      scales:{{
        x:{{title:{{display:true,text:'Age'}},min:0,max:95}},
        y:{{title:{{display:true,text:scoreLabel}},min:scoringMode==='decile'?0:30,max:100}}
      }}
    }}
  }});

  // ── Team scores by club (horizontal bar) ──────────────────────────────────
  const clubScores = useClubsAll.filter(c=>c.n_races>=1).slice(0,12);
  const csLabels = clubScores.map(c=>trunc(c.club,30));
  const csData = clubScores.map(c=>Math.round(c.total_score/c.n_races));
  const csColors = clubScores.map(c=>ageColor(c.mean_scoring_age||40));
  // Highlight selected club
  const csBorders = clubScores.map(c=>c.club===activeClub?'rgba(255,255,255,.9)':'transparent');
  const csBorderW = clubScores.map(c=>c.club===activeClub?2:0);

  charts.clubBar = new Chart(document.getElementById('club-chart'), {{
    type:'bar',
    data:{{labels:csLabels,datasets:[{{
      label:'Avg team score per race',
      data:csData,
      backgroundColor:csColors,
      borderColor:csBorders,
      borderWidth:csBorderW,
      borderRadius:4,
    }}]}},
    options:{{
      indexAxis:'y', responsive:true,
      plugins:{{
        legend:{{display:false}},
        tooltip:{{callbacks:{{
          label:ctx=>{{
            const c=clubScores[ctx.dataIndex];
            return [`Avg score: ${{csData[ctx.dataIndex]}}`,`Mean scoring age: ${{c.mean_scoring_age}}`,`Races: ${{c.n_races}}`,`Members: ${{c.n_members}}`];
          }}
        }}}}
      }},
      scales:{{
        x:{{title:{{display:true,text:'Avg Team Score per Race'}}}},
        y:{{grid:{{display:false}}}}
      }}
    }}
  }});

  // ── Scoring age profile ───────────────────────────────────────────────────
  // Clubs sorted lowest→highest score so ci=0 is at bottom, ci=n-1 at top.
  // This lets y=ci map directly to labels[ci] without any index arithmetic.
  const profileClubsRaw = activeClub
    ? useClubsAll.filter(c=>c.club===activeClub)
    : useClubsAll.filter(c=>c.n_races>=2).slice(0,10);
  const profileClubs = [...profileClubsRaw].reverse(); // lowest scorer first
  const profileLabels = profileClubs.map(c=>trunc(c.club,30));
  const profilePts = [];
  profileClubs.forEach((c,ci) => {{
    const label = profileLabels[ci];
    const clubTeams = useTeamsAll.filter(t=>t.club===c.club && t.valid);
    clubTeams.forEach(t => {{
      t.scorers.forEach(s => {{
        profilePts.push({{x:s.age, y:label, club:c.club, gender:s.gender, name:s.name, race:t.race, ap:s.ap_pct}});
      }});
    }});
  }});

  const mProf = profilePts.filter(d=>d.gender==='M').map(d=>({{x:d.x,y:d.y,_d:d}}));
  const fProf = profilePts.filter(d=>d.gender==='F').map(d=>({{x:d.x,y:d.y,_d:d}}));

  charts.ageProfile = new Chart(document.getElementById('age-profile'), {{
    type:'scatter',
    data:{{datasets:[
      {{label:'Male',data:mProf,backgroundColor:'rgba(78,154,241,.5)',pointRadius:5,pointHoverRadius:8}},
      {{label:'Female',data:fProf,backgroundColor:'rgba(241,107,138,.5)',pointRadius:5,pointHoverRadius:8}},
    ]}},
    options:{{
      responsive:true,
      plugins:{{
        legend:{{position:'bottom'}},
        tooltip:{{callbacks:{{
          label:ctx=>{{const d=ctx.raw._d; return [`${{d.name}} (age ${{d.x}})`,`${{d.club}}`,`AP% ${{d.ap}} | ${{d.race}}`];}}
        }}}}
      }},
      scales:{{
        x:{{title:{{display:true,text:'Age'}},min:10,max:95}},
        y:{{type:'category', labels:profileLabels, grid:{{display:false}}}}
      }}
    }}
  }});

  // ── Club standings table ──────────────────────────────────────────────────
  document.getElementById('club-tbody').innerHTML = clubs.map((c,i)=>
    `<tr style="${{c.club===activeClub?'background:var(--surface2)':''}}">
      <td>${{i+1}}</td>
      <td>${{c.club}}</td>
      <td style="font-weight:600;color:var(--green)">${{c.total_score.toFixed(1)}}</td>
      <td>${{c.best_score.toFixed(1)}}</td>
      <td>${{c.n_races}}</td>
      <td>${{c.n_members}}</td>
      <td>${{c.mean_ap}}%</td>
      <td>${{c.mean_age}}</td>
      <td style="color:${{c.mean_scoring_age&&c.mean_scoring_age>50?'var(--orange)':'var(--blue)'}}">${{c.mean_scoring_age||'\\u2014'}}</td>
      <td>${{c.n_male}} / ${{c.n_female}}</td>
    </tr>`
  ).join('');

  // ── All results table ─────────────────────────────────────────────────────
  document.getElementById('decile-col-header').style.display = scoringMode==='decile' ? '' : 'none';
  const sortedPerfs = [...perfs].sort((a,b)=>getScore(b,scoringMode)-getScore(a,scoringMode));
  document.getElementById('all-tbody').innerHTML = sortedPerfs.map(p=>
    `<tr>
      <td>${{p.name}}</td>
      <td>${{p.age}}</td>
      <td><span class="badge badge-${{p.gender}}">${{p.gender}}</span></td>
      <td>${{p.club}}</td>
      <td>${{p.race}}</td>
      <td>${{p.place}}</td>
      <td style="font-weight:600">${{p.ap_pct.toFixed(1)}}%</td>
      ${{scoringMode==='decile' ? `<td style="font-weight:600;color:var(--purple)">${{p.decile_pct.toFixed(1)}}%</td>` : ''}}
    </tr>`
  ).join('');

  // ── Experimental: model comparison ────────────────────────────────────────
  // Compute all three models for comparison
  const apTeams = recomputeTeams(allPerfs, 'ap');
  const decTeams = recomputeTeams(allPerfs, 'decile');
  const y35Teams = recomputeTeams(allPerfs, 'youth35');

  function computeStandings(teamsArr) {{
    const clubSet = [...new Set(teamsArr.filter(t=>t.valid).map(t=>t.club))];
    return clubSet.map(club => {{
      const valid = teamsArr.filter(t=>t.club===club && t.valid);
      const scores = valid.map(t=>t.score).sort((a,b)=>b-a);
      const best8 = scores.slice(0,8);
      const total = Math.round(best8.reduce((s,v)=>s+v,0)*10)/10;
      const ages = valid.flatMap(t=>t.scorers.map(s=>s.age));
      const meanAge = ages.length ? Math.round(ages.reduce((s,a)=>s+a,0)/ages.length*10)/10 : null;
      return {{club, total, meanAge}};
    }}).sort((a,b)=>b.total-a.total).map((s,i) => ({{...s, rank:i+1}}));
  }}

  const apStandings = computeStandings(apTeams);
  const decStandings = computeStandings(decTeams);
  const y35Standings = computeStandings(y35Teams);

  // Rank shift chart — show both alternative models vs official (all clubs)
  const compClubs = apStandings.map(s => {{
    const dec = decStandings.find(d=>d.club===s.club);
    const y35 = y35Standings.find(d=>d.club===s.club);
    if (!dec || !y35) return null;
    return {{club: s.club, apRank: s.rank, decRank: dec.rank, y35Rank: y35.rank,
             decShift: s.rank - dec.rank, y35Shift: s.rank - y35.rank, meanAge: s.meanAge}};
  }}).filter(Boolean).sort((a,b) => b.decShift - a.decShift);

  const shiftLabels = compClubs.map(c=>trunc(c.club,35));

  charts.rankShift = new Chart(document.getElementById('rank-shift'), {{
    type:'bar',
    data:{{labels:shiftLabels,datasets:[
      {{label:'Decade Pctile shift',data:compClubs.map(c=>c.decShift),
        backgroundColor:'rgba(167,139,250,.6)',borderRadius:3}},
      {{label:'Youth Req. shift',data:compClubs.map(c=>c.y35Shift),
        backgroundColor:'rgba(245,197,66,.6)',borderRadius:3}},
    ]}},
    options:{{
      indexAxis:'y', responsive:true,
      plugins:{{
        legend:{{position:'bottom',labels:{{color:'#8892a4',font:{{size:11}}}}}},
        tooltip:{{callbacks:{{
          label:ctx=>{{
            const c=compClubs[ctx.dataIndex];
            const shift = ctx.datasetIndex===0 ? c.decShift : c.y35Shift;
            const newRank = ctx.datasetIndex===0 ? c.decRank : c.y35Rank;
            return [`AP% rank: ${{c.apRank}}  →  rank: ${{newRank}}`,`Shift: ${{shift>0?'+':''}}${{shift}}`,`Mean scoring age: ${{c.meanAge}}`];
          }}
        }}}}
      }},
      scales:{{
        x:{{title:{{display:true,text:'Rank improvement vs official AP% (positive = better)'}}}},
        y:{{grid:{{display:false}}}}
      }}
    }}
  }});

  // Model comparison table — all three models
  const compRows = apStandings.map(s => {{
    const dec = decStandings.find(d=>d.club===s.club);
    const y35 = y35Standings.find(d=>d.club===s.club);
    if (!dec || !y35) return null;
    return {{club: s.club, apTotal: s.total, apRank: s.rank,
             decTotal: dec.total, decRank: dec.rank, decShift: s.rank - dec.rank,
             y35Total: y35.total, y35Rank: y35.rank, y35Shift: s.rank - y35.rank,
             meanAge: s.meanAge}};
  }}).filter(Boolean).sort((a,b)=>a.apRank-b.apRank);

  document.getElementById('model-comparison-tbody').innerHTML = compRows.map(r => {{
    const decColor = r.decShift > 0 ? 'var(--green)' : r.decShift < 0 ? 'var(--pink)' : 'var(--muted)';
    const y35Color = r.y35Shift > 0 ? 'var(--green)' : r.y35Shift < 0 ? 'var(--pink)' : 'var(--muted)';
    const ageCol = r.meanAge && r.meanAge > 50 ? 'var(--orange)' : 'var(--blue)';
    return `<tr>
      <td>${{r.club}}</td>
      <td>${{r.apTotal.toFixed(1)}}</td>
      <td>${{r.apRank}}</td>
      <td>${{r.decTotal.toFixed(1)}}</td>
      <td style="font-weight:700;color:${{decColor}}">${{r.decShift>0?'+':''}}${{r.decShift}}</td>
      <td>${{r.y35Total.toFixed(1)}}</td>
      <td style="font-weight:700;color:${{y35Color}}">${{r.y35Shift>0?'+':''}}${{r.y35Shift}}</td>
      <td style="color:${{ageCol}}">${{r.meanAge||'—'}}</td>
    </tr>`;
  }}).join('');
}}

// Initial render
render();

</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
