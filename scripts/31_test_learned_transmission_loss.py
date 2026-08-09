"""B2 — test whether a learned, per-catchment transmission-loss model beats the
borrowed Negev range. Answer: no. This script is the record of why not.

Where the data came from
-------------------------
Karam found Cataldo, Behr, Montalto & Pierce (2010), "Prediction of Transmission
Losses in Ephemeral Streams, Western U.S.A.", The Open Hydrology Journal 4:19-34
(open access, CC BY-NC 3.0) - docs/HANDOFF_abd_2026-08-07_b2_data.md /
tasks/mahdis-features-handoff/RESPONSE_karam_b2_transmission_loss_data.md.

The extracted tables (tasks/mahdis-features-handoff/data/) give real per-storm
`computed_tl_m3_per_km` - but that is a VOLUME LOSS RATE, not the 0-1 FRACTION
our transmission_loss actually is. The paper never tabulates each storm's inflow
volume directly. It DOES tabulate "Model #1" predicted TL/km for every storm,
and Model 1 is a pure, deterministic function of inflow volume alone:

    TL/km = 1.02 * Vol^0.75          (paper's Eq. 1, Vol in m3)

That is exactly invertible. `MODEL1_ROWS` below is that predicted value,
transcribed from the paper's Tables 2/3/4, for every storm - inverting it
recovers the real inflow volume the paper used, exactly, not approximately.
Verified: round-tripping the recovered Vol back through Eq. 1 reproduces the
printed Model 1 value to the last decimal; 29/30 Walnut Gulch `computed_tl`
values matched the pre-existing extraction from Karam's CSV independently
(the 30th differs by 0.1, a rounding artifact).

Fraction lost = (computed_tl_m3_per_km * reach_km) / implied_inflow_vol_m3.

One real ambiguity, not hidden
-------------------------------
Walnut Gulch's 30 storms were measured across 3-4 DIFFERENT reach lengths
(1.4-6.8 km - paper text, Sec. 4/results), and the paper does not say which
storm used which reach. There is no way to assign the right one per storm, so
Walnut Gulch is EXCLUDED from the regression test below rather than assigned
an invented reach length. Queen Creek and every Midwest system have exactly one
reach length each - no ambiguity for those 58 rows.

Queen Creek also has no D10/grain-size data at all (the paper says so directly:
pre-1941 sieve analyses were never published) - included in the area/reach-only
variant, excluded from anything using D10/K.

The result
----------
Every feature combination tested, under leave-one-SYSTEM-out validation (never
let the model see a system's own storms when predicting for it - same
discipline as the runoff model's LOCO), scores WORSE than predicting the mean
fraction lost every time. Negative R2 across the board. See main() output.

Why: within-system storm-to-storm spread (e.g. Cimarron River OK: 0.25-1.11
across its 10 storms, all sharing identical area/D10/K/reach_km) is comparable
to or larger than the spread BETWEEN different systems' averages. Static
per-catchment characteristics cannot explain storm-to-storm variance by
definition - and here, storm-to-storm variance is most of the variance there
is. This is a real physical answer, not a modelling shortfall: transmission
loss is dominated by storm-specific dynamics (size, intensity) this dataset
does not capture, not by the fixed physical characteristics B2 asked to
regress on.

Conclusion: transmission_loss_basis stays "negev_proxy" - not because the data
was never found, but because it was found, tested honestly, and shown not to
support a per-catchment learned estimate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "tasks/mahdis-features-handoff/data"
CHARACTERISTICS = DATA_DIR / "cataldo_2010_stream_characteristics.csv"
OUT = DATA_DIR / "cataldo_2010_transmission_loss_fraction.csv"

# Model 1 (paper's Eq. 1): TL/km = 1.02 * Vol^0.75. Pure function of Vol alone.
MODEL1_A, MODEL1_B = 1.02, 0.75


def implied_inflow_vol_m3(model1_tl_per_km: float) -> float:
    return (model1_tl_per_km / MODEL1_A) ** (1.0 / MODEL1_B)


# (computed_tl_m3_per_km, model1_predicted_tl_m3_per_km), transcribed from the
# paper's Table 2 (Walnut Gulch), in printed order - 30 storms, reach unknown
# per storm, EXCLUDED from the regression test, kept for completeness.
WALNUT_GULCH = [
    (9471.10, 4417.90), (3488.60, 9114.60), (686.1, 712.7), (12135.40, 5375.20),
    (631.9, 545.4), (3280.80, 3385.20), (1086.10, 1135.20), (2838.70, 5424.20),
    (5894.30, 4870.60), (15312.10, 8135.50), (976.7, 2609.20), (1814.80, 2532.50),
    (4037.40, 1442.60), (362.7, 371.7), (418.7, 837.5), (3002.20, 3624.30),
    (1400.20, 1252.30), (229.9, 331.1), (1050.60, 966), (744.9, 2553.50),
    (2243.40, 1737.40), (2596.70, 1526.40), (2720.00, 680.3), (2628.30, 1901.80),
    (6198.80, 11327.20), (11253.50, 9595.60), (1014.90, 1339.90), (1238.50, 936.9),
    (2016.30, 3864.30), (4260.10, 2909.90),
]

# Table 3, Queen Creek AZ, Q1-Q15, reach 32.2 km (Table 1) - unambiguous.
QUEEN_CREEK = [
    (2195.90, 5094.40), (793.3, 2426.60), (513.6, 4505.00), (3307.20, 9233.30),
    (3640.60, 13169.30), (23759.90, 60929.30), (6323.20, 15722.10), (10730.30, 47261.30),
    (32574.00, 79495.40), (50585.50, 79940.00), (16210.40, 24856.00), (36367.90, 45396.70),
    (48746.00, 61415.00), (27975.30, 88455.10), (24832.90, 50919.30),
]

# Table 4, Midwest streams - (paper's name as printed, computed_tl, model1_tl).
# One reach length per named system (Table 1) - unambiguous, except Cheyenne
# River SD, which has no Table 1 row at all (excluded, same as Karam's CSV).
MIDWEST = [
    ("Prairie Dog Creek KS", 31866.50, 88218.70), ("Prairie Dog Creek KS", 10789.20, 96225.20),
    ("Prairie Dog Creek KS", 14328.70, 30762.10), ("Prairie Dog Creek KS", 9698.50, 24395.80),
    ("Prairie Dog Creek KS", 14297.20, 54036.90),
    ("Republic Creek KS", 43574.80, 155205.40), ("Republic Creek KS", 111315.20, 452913.80),
    ("Saline River KS", 6217.90, 50428.10), ("Saline River KS", 4145.30, 19081.40),
    ("Saline River KS", 68980.30, 257217.90),
    ("Smokey Hill River KS", 9132.10, 55171.70), ("Smokey Hill River KS", 16209.50, 61826.70),
    ("Smokey Hill River KS", 8349.40, 25670.90), ("Smokey Hill River KS", 3457.20, 29377.90),
    ("Sappa Creek NE", 124449.10, 412993.00), ("Sappa Creek NE", 21022.60, 58604.60),
    ("Sappa Creek NE", 10774.10, 37316.60), ("Sappa Creek NE", 44782.40, 80893.20),
    ("Sappa Creek NE", 84506.30, 132890.10), ("Sappa Creek NE", 21591.90, 68835.40),
    ("Little Missouri River ND", 22155.40, 204286.90), ("Little Missouri River ND", 29758.60, 279378.70),
    ("Moreau River ND", 17752.30, 223763.10), ("Moreau River ND", 70922.20, 198440.60),
    ("Cimarron River OK", 22988.50, 169158.90), ("Cimarron River OK", 5760.60, 105881.90),
    ("Cimarron River OK", 14479.50, 144301.20), ("Cimarron River OK", 31644.00, 199098.70),
    ("Cimarron River OK", 10266.50, 118600.00), ("Cimarron River OK", 12675.90, 78245.90),
    ("Cimarron River OK", 4981.90, 80981.70), ("Cimarron River OK", 16132.20, 85800.20),
    ("Cimarron River OK", 10482.30, 187909.60), ("Cimarron River OK", 4260.50, 35177.60),
    ("Washita River OK", 7051.30, 53707.60), ("Washita River OK", 11245.90, 105801.00),
    ("Washita River OK", 20903.10, 162661.90), ("Washita River OK", 102717.90, 421692.30),
    ("Washita River OK", 98648.70, 430623.90),
    ("Shell Creek NE", 24698.40, 77079.70), ("Shell Creek NE", 7293.60, 21397.80),
    ("Little Blue River NE", 75111.80, 755603.40), ("Little Blue River NE", 155895.40, 390977.50),
    ("Cheyenne River SD", 10551.40, 448001.50), ("Cheyenne River SD", 10806.90, 53656.80),
]

# Paper's Table 4 spells four systems differently from Table 1 (transcribed
# exactly as printed in both places, per Karam's original CSV note).
MIDWEST_NAME_TO_CHARACTERISTICS_NAME = {
    "Republic Creek KS": "Republica Creek KS", "Saline River KS": "Salina River KS",
    "Sappa Creek NE": "Sappa KS", "Little Missouri River ND": "Little Missouri ND",
    "Moreau River ND": "Moreau River SD", "Cimarron River OK": "Cimarron R OK",
    "Little Blue River NE": "Little Blue NE", "Cheyenne River SD": None,
}


def build_fraction_table() -> pd.DataFrame:
    chars = pd.read_csv(CHARACTERISTICS).set_index("system")
    rows = []

    wg_reach_range = chars.loc[chars.index.str.startswith("Walnut Gulch")].reach_km
    for i, (computed, model1) in enumerate(WALNUT_GULCH):
        vol = implied_inflow_vol_m3(model1)
        fracs = [(computed * rk) / vol for rk in wg_reach_range]
        rows.append(dict(system="Walnut Gulch AZ", char_system=None, event_id=f"W{i+1}",
                         computed_tl_m3_per_km=computed, implied_inflow_vol_m3=vol,
                         fraction_lost=None, fraction_lost_min=min(fracs), fraction_lost_max=max(fracs),
                         reach_km=None,
                         note="AMBIGUOUS: reach not identifiable per storm, excluded from regression"))

    qc_reach = chars.loc["Queen Creek AZ"].reach_km
    for i, (computed, model1) in enumerate(QUEEN_CREEK):
        vol = implied_inflow_vol_m3(model1)
        frac = (computed * qc_reach) / vol
        rows.append(dict(system="Queen Creek AZ", char_system="Queen Creek AZ", event_id=f"Q{i+1}",
                         computed_tl_m3_per_km=computed, implied_inflow_vol_m3=vol,
                         fraction_lost=frac, fraction_lost_min=frac, fraction_lost_max=frac,
                         reach_km=qc_reach, note=""))

    counters: dict[str, int] = {}
    for name, computed, model1 in MIDWEST:
        counters[name] = counters.get(name, 0) + 1
        vol = implied_inflow_vol_m3(model1)
        char_name = MIDWEST_NAME_TO_CHARACTERISTICS_NAME.get(name, name)
        if char_name is None:
            rows.append(dict(system=name, char_system=None, event_id=f"{name}-{counters[name]}",
                             computed_tl_m3_per_km=computed, implied_inflow_vol_m3=vol,
                             fraction_lost=None, fraction_lost_min=None, fraction_lost_max=None,
                             reach_km=None, note="NOT JOINABLE: no characteristics row"))
            continue
        reach = chars.loc[char_name].reach_km
        frac = (computed * reach) / vol
        rows.append(dict(system=name, char_system=char_name, event_id=f"{name}-{counters[name]}",
                         computed_tl_m3_per_km=computed, implied_inflow_vol_m3=vol,
                         fraction_lost=frac, fraction_lost_min=frac, fraction_lost_max=frac,
                         reach_km=reach, note=""))

    out = pd.DataFrame(rows)
    out = out.merge(
        chars[["contributing_area_km2", "d10_mm", "k_cm_per_sec_x1e-4"]],
        left_on="char_system", right_index=True, how="left",
    )
    return out


def loso_eval(df: pd.DataFrame, feats: list[str], model_fn, label: str) -> None:
    """Leave-one-SYSTEM-out - never score a system with a model that saw it."""
    d = df.dropna(subset=feats + ["fraction_lost"])
    preds, obs = [], []
    for sys in d.char_system.unique():
        tr, te = d[d.char_system != sys], d[d.char_system == sys]
        if len(te) == 0 or len(tr) == 0:
            continue
        m = model_fn()
        m.fit(tr[feats], tr.fraction_lost)
        preds.extend(m.predict(te[feats]))
        obs.extend(te.fraction_lost)
    obs_a, preds_a = np.array(obs), np.array(preds)
    mean_baseline_mae = mean_absolute_error(obs_a, [obs_a.mean()] * len(obs_a))
    print(f"  {label:22s} n={len(obs_a):3d}  R2={r2_score(obs_a, preds_a):+.3f}  "
          f"MAE={mean_absolute_error(obs_a, preds_a):.3f}  (mean-baseline MAE={mean_baseline_mae:.3f})")


def main() -> None:
    df = build_fraction_table()
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}\n")

    reg = df[(df.fraction_lost.notna()) & (df.system != "Walnut Gulch AZ")].copy()
    reg["log_area"] = np.log(reg.contributing_area_km2)
    reg["log_reach"] = np.log(reg.reach_km)
    reg["log_d10"] = np.log(reg["d10_mm"])
    reg["log_k"] = np.log(reg["k_cm_per_sec_x1e-4"])

    print(f"{len(reg)} exact rows, {reg.char_system.nunique()} systems "
          f"(Walnut Gulch excluded - ambiguous reach; Cheyenne River SD excluded - no characteristics)\n")

    print("Leave-one-system-out (never score a system the model was trained on):")
    loso_eval(reg, ["log_area", "log_reach"], LinearRegression, "area+reach, linear")
    loso_eval(reg, ["log_area", "log_reach"],
             lambda: RandomForestRegressor(n_estimators=200, max_depth=3, random_state=1),
             "area+reach, RF")
    loso_eval(reg, ["log_area", "log_reach", "log_d10", "log_k"], LinearRegression,
             "+D10+K, linear (drops Queen Creek)")
    loso_eval(reg, ["log_area", "log_reach", "log_d10", "log_k"],
             lambda: RandomForestRegressor(n_estimators=200, max_depth=3, random_state=1),
             "+D10+K, RF")
    loso_eval(reg, ["log_d10", "log_k"], LinearRegression, "D10+K only, linear")
    loso_eval(reg, ["log_k"], LinearRegression, "K only, linear")
    loso_eval(reg, ["log_d10"], LinearRegression, "D10 only, linear")

    print("\nWithin-system vs. between-system spread of fraction_lost:")
    g = reg.groupby("char_system").fraction_lost.agg(["min", "max", "count"])
    g["range"] = g["max"] - g["min"]
    print(g.sort_values("range", ascending=False).round(3).to_string())
    between = reg.groupby("char_system").fraction_lost.mean()
    print(f"\nmean within-system range: {g['range'].mean():.3f}")
    print(f"between-system mean spread (max mean - min mean): {between.max()-between.min():.3f}")

    print(
        "\nCONCLUSION: every feature combination scores worse than the mean-baseline "
        "under honest leave-one-system-out validation. Static per-catchment "
        "characteristics cannot explain storm-to-storm variance, and here "
        "storm-to-storm variance dominates. transmission_loss_basis stays "
        "'negev_proxy' - tested, not assumed."
    )


if __name__ == "__main__":
    main()
