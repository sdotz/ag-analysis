# VDOT vs Age Grade Analysis

An analysis tool comparing two methods of evaluating running performance across ages, genders, and distances:

- **VDOT** — Jack Daniels' measure of aerobic capacity, derived directly from race time and distance. Age-blind.
- **Age Grade %** — A performance expressed as a percentage of the world-record standard for the same age and gender. Explicitly age-adjusted.

The core question: *where do these two metrics agree, and where do they diverge?*

## Data

`msab/men/` and `msab/women/` contain Masters All-Age Best (MSAB) performances across 12 distances:

Mile · 5K · 8K · 10K · 12K · 15K · 10 Mile · 20K · Half Marathon · 25K · 30K · Marathon

Each CSV has one row per age-group record with columns: `Event`, `Gender`, `Age`, `Time`, `TIME_SEC`, athlete info, race metadata, and a computed `VDOT` column.

## Scripts

### `compute_vdot.py`
Computes VDOT for every performance using the Jack Daniels formula and writes it back as a `VDOT` column.

```
python compute_vdot.py                  # men (msab/men/)
python compute_vdot.py msab/women       # women
```

VDOT formula:
```
v       = distance_m / time_min
vo2     = -4.60 + 0.182258·v + 0.000104·v²
pct_max = 0.8 + 0.1894393·e^(-0.012778·t) + 0.2989558·e^(-0.1932605·t)
VDOT    = vo2 / pct_max
```

### `age_grade.py`
Python port of `age_grade_calc/AgeGradeCalculator.swift`. Loads the WMA age-factor tables from `age_grade_calc/RunScore/` and computes age-grade results for any distance, time, age, and gender.

```python
from age_grade import AgeGradeCalculator
ag = AgeGradeCalculator()
result = ag.result(distance_m=5000, time_sec=1140, age=45, gender='M')
print(result.percentage)   # e.g. 78.4
```

### `analyze_vdot_vs_ag.py`
Loads all performances, computes within-(gender, distance) percentile ranks for both VDOT and AG%, and reports:

- Overall Spearman ρ between the two ranking systems
- Correlation and rank-delta spread by distance and gender
- Age-band divergence — the U-shaped pattern showing where each metric over- or under-rewards

```
python analyze_vdot_vs_ag.py
```

## Explorer

`vdot_ag_explorer.html` is a self-contained single-page app with all 1,766 performances embedded. Open it in any browser — no server needed.

**Charts**
- Scatter of VDOT vs AG% coloured by gender, with per-point tooltips
- Spearman ρ by distance (longer races agree more)
- Rank-delta spread by distance (shorter races diverge more)
- Age-band divergence line — reacts to all filters

**Filters** (all live)
- Gender toggle
- Distance selector
- Age range slider

**Table** — sortable, name-searchable, paginated; Δ rank column shows where each method rewards the performance more.

## Key Findings

| Finding | Detail |
|---|---|
| Overall agreement | ρ = 0.58 — moderate, not strong |
| Best agreement | Long distances (30K, Marathon): ρ ≈ 0.85 |
| Most disagreement | Short distances (Mile, 5K, 10 Mile): ρ ≈ 0.30–0.50 |
| Age effect | U-shaped: AG over-rewards ages ≤9 and 60+; VDOT over-rewards prime-age 20–39 |
| Gender | Men agree more (ρ = 0.63) than women (ρ = 0.53) |

The U-shaped age pattern is the clearest signal: age-grade factors give children and masters athletes more credit than their raw aerobic capacity (VDOT) warrants, while prime-age runners rank higher on VDOT than their age-adjusted world-standard comparison reflects.

## Requirements

```
pip install -r requirements.txt  # pandas, numpy
```

The original `running_calculator/` package (Jack Daniels VDOT lookup tables and pace calculators) is also included.
