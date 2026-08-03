# Handoff to Mahdi — 3 August 2026

Karam. Your training data is ready and it is **11× bigger than it was this morning**.
Three days to the 6 August vertical slice, ten to the deadline.

There is one thing in here that will cost you a day if you miss it: **§2, the target
definition.** Read that before you train anything.

---

## 1 · Exactly where the data is and how to load it

Two files. **Features in one, labels in the other** — deliberately, so a label can never
be used as an input by accident.

```
data/processed/features/event_catchment_features.parquet     500 rows x 139 cols   FEATURES (X)
data/processed/features/event_antecedents.parquet            395 rows,  15 cols    LABELS  (y)
data/processed/features/event_antecedents.summary.json                             label stats + warnings
```

Copy-paste this. It is the whole loading step:

```python
import pandas as pd

X = pd.read_parquet("data/processed/features/event_catchment_features.parquet")
y = pd.read_parquet("data/processed/features/event_antecedents.parquet")

KEYS = ["event_id", "catchment_id"]          # the join. Both files use these two.

df = X.merge(y[KEYS + ["label_surface_runoff_mm"]], on=KEYS, how="inner")
df = df.dropna(subset=["label_surface_runoff_mm"])
print(len(df), "trainable rows")             # ~390

# Never let a label into the features.
feature_cols = [c for c in X.columns
                if c not in KEYS
                and not c.startswith("label_")
                and c not in ("date", "storm_start", "storm_end", "merged_event_ids",
                              "event_date", "selection_reason", "wettest_catchment")]
```

**`inner` is correct here**, not `left`: 105 of the 500 feature rows have no label yet
because their ERA5 month is still downloading, and a row with no target cannot train.

**Nothing else needs joining.** Terrain, soil, landcover, urban and the antecedent
features are already merged into `event_catchment_features.parquet`. You do not need to
touch the five source files.

### Do not read this from Supabase

The database has the same tables, but as of today `events` holds **116** rows and
`event_catchment_features` holds **580** — 16 of those events are duplicate storm-days
that I merged away this morning, and they drag 80 duplicate feature rows with them.
Training off the DB would put the same storm in train *and* test. **Use the parquet
files.** I am cleaning the DB separately.

| | this morning | now |
|---|---:|---:|
| labelled events | 7 | **79** |
| labelled rows | 35 | **395** |
| feature columns | 128 | **139** |

| | this morning | now |
|---|---:|---:|
| labelled events | 7 | **79** |
| labelled rows | 35 | **395** |
| feature columns | 128 | **139** |

What changed: the antecedent extraction had not been re-run since 74 ERA5 month-files
landed, and `antecedent` was named as a source in the matrix builder's docstring but never
actually registered — so the matrix was shipping **without soil moisture or prior
rainfall**, the event-varying predictors, while looking complete. Both fixed.

105 of the 500 rows have `NaN` antecedents because their ERA5 month has not downloaded
yet. They are left in place as NaN deliberately — a shrinking row count is far harder to
notice than a NaN column. The sweep is at 74 of 84 months and still running, so this
number improves on its own. **Re-run `extract_event_antecedents.py` then
`build_feature_matrix.py` before your final training run** and you will get more rows for
free.

---

## 2 · Do not binarise the label at `> 0`

This is the important part.

Candidates are already the top ~1% of days by rainfall, so almost every one produces
*some* ERA5 runoff. At a zero threshold:

```
98% of rows are positive
```

A model that predicts "runoff" every single time scores **~98% accuracy**. It has learned
nothing. This is the same tautology the label rule exists to prevent, arriving from the
opposite direction — and unlike a leaked feature, **it will not look like a bug.** It will
look like an excellent result, and it will fall apart the moment someone asks it a
question in the Q&A.

The **magnitude** is what carries the signal. It spans four orders of magnitude, and
within one catchment the max is ~19× the median.

| threshold | value (mm) | positive |
|---|---:|---:|
| `> 0` | 0 | **98%** ← do not use |
| `> p50` | 0.00584 | 50% |
| `> p75` | 0.01624 | 25% |
| `> p90` | 0.03897 | 10% |

**Two defensible options:**

- **Regression** on `label_surface_runoff_mm`. Use a log transform — it spans
  0.00003 to 0.198 mm.
- **Binary at a candidate-set percentile.** p50 gives a clean 50/50 split.

Either way the threshold is a modelling decision and belongs in **your model card**, not
buried in a script. Full distribution, per-catchment medians and both warnings are in
`event_antecedents.summary.json` under `label_distribution`, so you do not need to
recompute any of it.

Concretely, if you go binary:

```python
import numpy as np
THRESHOLD = np.percentile(df["label_surface_runoff_mm"], 50)   # ~0.0058 mm
df["target"] = (df["label_surface_runoff_mm"] > THRESHOLD).astype(int)
print(df["target"].mean())        # must be ~0.50, NOT ~0.98
```

**That printed number is your first sanity check.** If it comes out near 0.98 you have
used `> 0` and every score after it is meaningless.

### Weak predictors — know this before you set expectations

Correlations of the antecedent features against runoff magnitude are honest but weak:

```
precipitation_prior_24h_mm     r = +0.17
soil_moisture_t_minus_24h      r = +0.05
precipitation_prior_7d_mm      r = +0.04
```

`precipitation_depth_mm` (the event's own rainfall) is the feature to lean on. If your
XGBoost barely beats the rule baseline, that may be the honest answer rather than a bug —
which is exactly why your DoD asks for **the baseline's score reported honestly**. A
rule baseline that wins is a publishable result here, not a failure.

---

## 3 · Leakage — why LOCO is not optional

Per-catchment median runoff orders monotonically with catchment area:

| catchment | area km² | median runoff mm |
|---|---:|---:|
| AQ-C01 | 4,453 | 0.0104 |
| AQ-C02 | — | 0.0078 |
| AQ-C03 | — | 0.0061 |
| AQ-C04 | — | 0.0051 |
| AQ-C05 | — | 0.0047 |

Combined with static features that are **constant per catchment** (terrain, soil,
landcover — 110 of your 139 columns), random K-fold CV will memorise catchment identity
and hand you a good score that means nothing. Five catchments, so LOCO is five folds.

**Both are required**: leave-one-catchment-out **and** a temporal holdout at train ≤2014.
They test different failures — LOCO tests transfer to an unseen catchment, the temporal
split tests transfer to an unseen climate period.

### How to verify — the exact recipe

```python
from sklearn.metrics import roc_auc_score

# ---- 1. the baseline you must beat, and must report even if it wins
majority = df["target"].mean()
print(f"majority-class accuracy: {max(majority, 1-majority):.3f}")   # beat this or say so

# ---- 2. leave-one-catchment-out: 5 folds, one per catchment
for held_out in sorted(df["catchment_id"].unique()):
    train = df[df["catchment_id"] != held_out]
    test  = df[df["catchment_id"] == held_out]
    # ... fit on train, predict on test ...
    print(held_out, "n_test =", len(test))

# ---- 3. temporal holdout: train on the past, test on the future
year  = pd.to_datetime(df["event_id"].str.slice(3, 13)).dt.year
train = df[year <= 2014]
test  = df[year >  2014]
print("temporal split:", len(train), "train /", len(test), "test")
```

**What a trustworthy result looks like:**

| signal | good | bad |
|---|---|---|
| target balance | ~0.50 | ~0.98 → you used `> 0` |
| accuracy vs majority baseline | a few points above | *far* above → suspect leakage |
| LOCO spread across the 5 folds | similar scores | one fold near-perfect → memorising that catchment |
| random CV vs LOCO | LOCO a bit worse | random CV *much* better → leakage confirmed |
| top features | some event-varying ones | all static → the model learned which catchment, not what happens |

**The single most useful check:** run plain random K-fold *as well as* LOCO. If random CV
scores much higher, that gap **is** the leakage, measured. Report both numbers — that
comparison is a stronger result than either score alone, and it is exactly the kind of
honesty that survives a judge's question.

If your XGBoost only ties the rule baseline, **say so and keep the baseline.** With 390
rows, 5 catchments and predictors this weak, a rule that wins is a legitimate finding.
Overselling a marginal model is the thing that loses the Q&A.

---

## 4 · Your DoD item 3 is already answered

> *"A stated verdict on the Oct-2016-ranking claim — held or not held."*

**Not held.** Measured, from the catalogue:

| ranking | Oct 2016 position |
|---|---|
| by daily total | 14th of 100 |
| by peak 3-hour intensity | **8th of 83** |
| by peak 3-h intensity for AQ-C01 specifically | 16th |

So it is **not** in the top 3. The expectation was written before the data existed.

What *is* true, and worth saying on the slide: it ranks **higher by intensity than by
daily total** (14th → 8th), which is the direction the literature predicts for an event
delivering 82% of its rainfall in an 18-hour spell. The event mattered because it was
intense on a dry catchment, not because it was large. That is a more interesting finding
than the original claim would have been.

Cite the numbers, not the expectation.

---

## 4b · Choose your columns — this is the real overfitting risk

390 labelled rows and 139 columns sounds like a row-count problem. It is not. Measured:

| | count | what it means |
|---|---:|---|
| **constant per catchment** | **115** | only **5 distinct values** in the entire table |
| **vary by event** | **14** | the only columns that can respond to a forecast |
| identifiers / artefacts | 9 | never train on these |

Those 115 columns — soil, terrain, landcover, urban — do not describe 390 situations. They
describe **five catchments**, repeated 78 times each. A tree splitting on
`soil_clay_0_5cm` is not learning about clay; it is learning *"this is AQ-C03"*. Random CV
will reward that richly. Leave-one-catchment-out will destroy it.

**More rows would not fix this.** Choosing columns does. So `feature_matrix_status.json`
now carries a `feature_roles` block and you can select instead of guess:

```python
import json
roles = json.load(open("data/processed/events/feature_matrix_status.json"))["feature_roles"]

roles["event_varying"]           # 14 — start here
roles["static_per_catchment"]    # 115 — add deliberately, a few at a time
roles["non_feature"]             # 9  — never
```

**Suggested progression**, each step reported:

1. **14 event-varying columns only.** ~390 rows, 14 features. Honest starting point.
2. Add **a handful** of static features you can justify physically — catchment area,
   mean slope, bare-ground fraction. Not all 115.
3. If LOCO gets *worse* when you add static features, they were memorisation. Stop.

### One column you must not train on

**`rank`** is now classified `non_feature`, and it is the subtle one. It is the storm's
position in *our* catalogue by rainfall, so it correlates strongly with runoff and will
look like your best predictor. **A live forecast has no rank** — you cannot know where
tomorrow's storm places among 27 years of history. A model using it scores well offline
and cannot be deployed, which is worse than a model that scores badly, because the score
hides the problem.

### If you genuinely want more rows

There is room, and it is my job not yours. The catalogue is the **top 100 storms**, cut off
at 3.26 mm daily. The full record holds:

| threshold | days |
|---|---:|
| ≥ 1 mm anywhere | **393** |
| ≥ 3 mm | 125 |
| ≥ 5 mm | 58 |

Aqaba is hyper-arid — only 393 of 10,135 days have measurable rain anywhere. So the
ceiling is roughly **250–300 storms after merging** consecutive days, i.e. about **3× the
current rows**. The added storms are 1–3 mm events that mostly produce no runoff, which
would actually *help* — the target is currently 98% positive, and genuine no-runoff cases
are what it lacks.

The cost is ERA5 downloads for the extra months, and the sweep is already the slow
dependency. **Tell me if you want it and I will start it** — decide after step 1 above,
because if 14 features on 390 rows already overfits, more rows of the same shape will not
rescue it.

---

## 5 · A correction to your task file

Your task file may still say the feature matrix is partially blocking you and to build
against a stub. **It is not blocking any more** — build against the real file.

One caveat that *is* still live: the matrix has 139 columns and 110 of them are static
per catchment. Feature-importance plots will be dominated by them for the leakage reason
in §3. Consider reporting importance separately for the ~15 event-varying features, which
are the only ones that can respond to a forecast.

---

## 6 · Docker is your biggest schedule risk, not the model

Your DoD item 6 is `docker compose up` producing a working demo **with wifi off**. There
is currently **no Dockerfile and no compose file in the repo**, and nothing of yours has
been pushed yet.

I would rather you had a container that boots with a mediocre model inside it than a
brilliant model that only runs on your laptop. Offline means:

- Every dataset the demo touches baked into the image or a mounted volume — `data/raw/`
  is git-ignored and **will not** arrive in a pull.
- No call to CDS, Harmony, Earth Engine, Supabase-over-the-internet or a tile server at
  runtime. The MapLibre basemap is the one people forget — Ali's map goes grey with wifi
  off unless tiles are bundled.
- A seeded database, not a migration that expects to reach the network.

If Docker is going to slip, tell me today rather than on the 12th. It is the single
failure that takes the whole demo down, and it is the one nobody can substitute for you
at the last minute.

---

## 7 · What I would do in order

1. **Harness + rule baseline** against the real 395 rows. Get an honest number on the
   board before touching XGBoost.
2. **Pick the target** per §2 and write the choice into the model card immediately.
3. **LOCO + temporal holdout** wired into the harness from the start, not added later.
4. **Dockerfile early**, even around a half-finished model. Item 6 is the risk.
5. XGBoost, calibrated, compared honestly against the baseline.
6. Predict function for Pulga's API + `model_versions` for Nizar.
7. Sediment proxy with transmission loss exposed.

Anything ambiguous at the seams is mine — ask rather than guess. Two specific ones:
`position_confidence` and the **AQ-O04 caveat** (it discharges into an enclosed harbour
basin, so a plume released there settles in the basin) must travel through to the API as
data, not as a note in a doc. Coordinate that with Pulga rather than each of you doing
half of it.

---

## 8 · What is still moving

- **ERA5 sweep: 74 of 84 months**, still running. More labelled events arrive on their
  own; re-run the two scripts in §1 before your final training run.
- **Reef zones changed today** — real Allen Coral Atlas habitat, total area 5.69 → 1.24 km².
  Does not affect you directly, but it changes every exposure number Pulga produces.
- **Supabase** is unreachable from my machine (IPv6-only direct host); Nizar owes a pooler
  string. Affects your `model_versions` write, not your training.
- **Abd's real plume mask** is still swap #4.
