# MLDR Road Age-Grading Calculator

Extracted and ported from
[https://www.howardgrubb.co.uk/athletics/mldrroad25.html](https://www.howardgrubb.co.uk/athletics/mldrroad25.html)
(Howard Grubb, 1999–2025).

This subdir lets us programmatically compute the same AP% values the
official calculator does, including the bilinear interpolation it applies
when the distance or age falls between tabulated entries.

## Contents

| File                  | What                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `source.html`         | Exact page as fetched (canonical source — do not edit).              |
| `mldr.js`             | The `<script>` block from `source.html`, extracted verbatim.         |
| `extract_factors.py`  | Parses `mldr.js` and emits `factors.py`. Re-run if the JS changes.   |
| `factors.py`          | Auto-generated. The 8 factor tables (MLDR 2025/2020, WMA 2015/2010). |
| `mldr.py`             | Python port of the calculator. Public API: `age_grade(...)`.         |
| `verify.py`           | Sanity-checks a handful of known cases (WRs, edges, interp).         |

## Use

```python
from mldr import age_grade, parse_time, DISTANCES_KM

r = age_grade(
    distance_km = DISTANCES_KM["1mi"],   # 1.609344
    time_sec    = parse_time("7:32"),    # 452.0
    age         = 82,
    gender      = "M",
    year        = 2025,                  # 2025 (default), 2020, 2015, 2010
)
print(r.ap_pct)        # 87.89
print(r.factor)        # 0.5714
print(r.age_graded_sec)  # 258.27  (=open-age equivalent)
```

Returns `None` if the distance is outside the tabulated range (the JS
calculator stopped extrapolating distances in June 2017). Age out of
range clamps to the nearest tabulated age (the JS does the same).

## AP% formula

For age factor *f* and open-age standard time *S*:

```
age_standard = S / f            # the standard time, adjusted for age
age_graded   = actual * f       # what the runner would have run open-age
AP%          = 100 * age_standard / actual
             = 100 * S / (actual * f)
```

## How interpolation works

Mirrors the JS:

- **Distance.** Two surrounding events bracket the chosen distance.
  `pfac = (dist - lo) / (hi - lo)`. Out-of-range → no result.
- **Age.** Two surrounding tabulated ages bracket the runner's age.
  `page = (age - lo) / (hi - lo)`. Out-of-range → clamp.
- **Factor.** Bilinear over (distance × age):

  ```
  f = (1-pfac) * [ page*f(lo_d, hi_a) + (1-page)*f(lo_d, lo_a) ]
    +    pfac  * [ page*f(hi_d, hi_a) + (1-page)*f(hi_d, lo_a) ]
  ```
- **Standard time** is interpolated linearly over distance only.

## Refreshing from the source

If Howard Grubb updates the page:

```sh
curl -sL https://www.howardgrubb.co.uk/athletics/mldrroad25.html -o source.html
awk '/^<script>/{f=1;next} /^<\/script>/{f=0} f' source.html > mldr.js
python extract_factors.py    # regenerates factors.py
python verify.py             # sanity-check
```
