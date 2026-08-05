"""Validate any day-ranker against the documented sea-reaching floods.

The measurement this project can actually make
----------------------------------------------
`scripts/23` established that the ERA5 runoff target is a rainfall mask, so no
metric computed against it means what we said it meant. The only trustworthy
reference is a day on which sediment is DOCUMENTED to have reached the sea, and
Kalman et al. (2025) says thirteen such days exist since 1994.

Thirteen positives cannot train anything. They can validate decisively, because
the null is brutal: flag the top 14 of 8,981 days and a random ranker expects
0.016 hits, so **two** hits is already p < 0.001. That asymmetry - useless for
training, powerful for validation - is the whole reason this script exists.

What it measures, and what it refuses to measure
------------------------------------------------
  recall@K       of the documented floods, how many land in the top K days
  p-value        hypergeometric, against a uniformly random ranker
  lift           observed hits / hits expected by chance

  PRECISION IS NOT COMPUTED, deliberately. The gold list is floods recorded at
  the Kinnet Canal on the ISRAELI shoreline; our catchments are Jordanian. A
  flagged day absent from the list may be a real Aqaba-side flood nobody
  recorded, so an unmatched flag is not a false positive and any precision
  figure would be a floor of unknown depth. See the location_caveat in
  docs/event_dates.md.

Honest reporting on a partial list
----------------------------------
Only 1 of the 13 dates is known today; the other 12 are behind two papers (see
docs/karam_handoff.md Request 0). The harness therefore prints power against
`total_documented` alongside results on `dates_confirmed`, so a run on n=1 reads
as "1 of 13 available" and never as "validated". It is built now so that the day
the dates arrive, validation is one command and not a week of scaffolding.

Rule 1 compliance: every date is parsed from the YAML block in
docs/event_dates.md. Nothing here hard-codes one.

Usage
    python scripts/24_gold_event_validation.py                    # sediment index
    python scripts/24_gold_event_validation.py --score era5_rain  # a rainfall ranker
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import hypergeom

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

EVENT_DATES = ROOT / "docs/event_dates.md"
TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
INTENSITY = ROOT / "data/processed/features/daily_intensity.parquet"
REPORT = ROOT / "reports/model/gold_event_validation.md"

# Budgets to report recall at. The first is the literature's own base rate, which
# is the only one with an external justification.
BUDGETS = [(0.00156, "literature base rate (13 in 22.8 yr)"),
           (0.005, "literature daily-probability ceiling"),
           (0.01, "1% of days"),
           (0.05, "5% of days")]


def load_gold() -> dict:
    """Parse the sea_reaching_flood_record block. Never hard-code a date."""
    text = EVENT_DATES.read_text()
    blocks = re.findall(r"```yaml\n(.*?)\n```", text, re.S)
    if not blocks:
        raise SystemExit(f"no yaml block in {EVENT_DATES}")
    for b in blocks:
        doc = yaml.safe_load(b)
        if isinstance(doc, dict) and "sea_reaching_flood_record" in doc:
            return doc["sea_reaching_flood_record"]
    raise SystemExit("sea_reaching_flood_record absent from docs/event_dates.md")


def power_table(n_days: int, n_gold: int) -> pd.DataFrame:
    """Hits needed for significance at each budget, under a random ranker."""
    rows = []
    for frac, label in BUDGETS:
        K = max(1, int(round(frac * n_days)))
        rv = hypergeom(n_days, n_gold, K)
        need = {a: next((k for k in range(n_gold + 1) if rv.sf(k - 1) < a), None)
                for a in (0.05, 0.001)}
        rows.append({
            "budget": label,
            "K days": K,
            "E[hits] by chance": round(float(rv.mean()), 3),
            "hits for p<0.05": need[0.05],
            "hits for p<0.001": need[0.001],
        })
    return pd.DataFrame(rows)


def evaluate(scores: pd.Series, gold: list[pd.Timestamp], n_gold_total: int):
    """Rank days by score; report recall@K and its hypergeometric p-value."""
    ranked = scores.sort_values(ascending=False)
    N = len(ranked)
    rank_of = {d: int(np.where(ranked.index == d)[0][0]) + 1
               for d in gold if d in ranked.index}
    unscorable = [d for d in gold if d not in ranked.index]

    rows = []
    for frac, label in BUDGETS:
        K = max(1, int(round(frac * N)))
        hits = sum(1 for r in rank_of.values() if r <= K)
        # p over the FULL documented set, not just the dates we happen to hold -
        # otherwise a lucky single confirmed date reads as significance.
        p = hypergeom(N, n_gold_total, K).sf(hits - 1) if hits else 1.0
        exp = n_gold_total * K / N
        rows.append({
            "budget": label, "K": K,
            "hits": hits, "of_confirmed": len(rank_of),
            "E[hits]": round(exp, 3),
            "lift": round(hits / exp, 1) if exp > 0 and hits else 0.0,
            "p": f"{p:.2e}" if p < 0.01 else f"{p:.3f}",
        })
    return pd.DataFrame(rows), rank_of, unscorable, N


def build_scores(which: str) -> pd.Series:
    """Score every day in the record. Storm-level, so summed across catchments."""
    df = pd.read_parquet(TRAIN)
    inten = pd.read_parquet(INTENSITY)[["date", "catchment_id",
                                        "era5_rain_mm_day"]]
    df = df.merge(inten, on=["date", "catchment_id"], how="left")

    if which == "sediment":
        from models.sediment_proxy import SedimentProxy
        df["s"] = SedimentProxy().index(df, df.sro_mm_day.to_numpy())
    elif which == "era5_rain":
        df["s"] = df.era5_rain_mm_day
    elif which == "imerg_rain":
        df["s"] = df.precipitation_mm_day
    else:
        raise SystemExit(f"unknown scorer {which}")
    return df.groupby("date").s.sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", default="sediment",
                    choices=["sediment", "era5_rain", "imerg_rain"])
    args = ap.parse_args()

    gold = load_gold()
    total = int(gold["total_documented"])
    confirmed = [pd.Timestamp(e["date"]) for e in gold.get("dates_confirmed", [])]
    pending = int(gold.get("dates_pending", {}).get("count", 0))

    print(f"gold set: {total} documented sea-reaching floods since "
          f"{gold['record_begins']}")
    print(f"  dates confirmed {len(confirmed)}   pending {pending}")
    if pending:
        print(f"  ** PARTIAL LIST — this is not a validation run. **")
        for b in gold["dates_pending"]["blocked_on"]:
            print(f"     blocked on {b['citation']}: {b.get('doi', b.get('journal'))}")
    print(f"\nmeasured at: {gold['measurement_location']}")
    print(f"  {gold['location_caveat'].strip()}\n")

    scores = build_scores(args.score)
    res, rank_of, unscorable, N = evaluate(scores, confirmed, total)

    print(f"=== ranker: {args.score} · {N:,} scorable days ===")
    if unscorable:
        print(f"  {len(unscorable)} confirmed date(s) NOT in the record and "
              f"therefore unscorable: {[str(d.date()) for d in unscorable]}")
        print("  (needs the ERA5 month for that date — see Request 1)")
    for d, r in sorted(rank_of.items()):
        print(f"  {d.date()}  rank {r:,} of {N:,}  "
              f"(top {100*r/N:.2f}%)")
    print()
    print(res.to_string(index=False))
    print(f"\npower against the FULL {total}-event set, random-ranker null:")
    print(power_table(N, total).to_string(index=False))
    print("\nprecision is not computed — see the location caveat above.")

    write_report(gold, args.score, res, rank_of, unscorable, N, total,
                 pending, confirmed)
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


def write_report(gold, which, res, rank_of, unscorable, N, total, pending,
                 confirmed):
    ranks = ("\n".join(f"| {d.date()} | {r:,} | {100*r/N:.2f}% |"
                       for d, r in sorted(rank_of.items()))
             or "| — | — | — |")
    status = (f"**PARTIAL — {len(confirmed)} of {total} dates known.** This is not "
              f"a validation run." if pending else
              f"**COMPLETE — all {total} dates known.**")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Gold-event validation — `{which}` ranker

**Date:** 4 August 2026 · `scripts/24_gold_event_validation.py`

{status}

The ERA5 runoff target is a rainfall mask (`reports/model/label_autopsy.md`), so
no metric against it means what we said it meant. The only trustworthy reference
is a day sediment is **documented** to have reached the sea. Kalman et al. (2025)
says {total} such days exist since {gold['record_begins']}:

> "{gold['source_quote']}"

{total} positives cannot train anything. They validate decisively, because the
null is brutal — see the power table below.

## Where the confirmed events rank

| date | rank of {N:,} | percentile |
|---|---:|---:|
{ranks}

{f"**{len(unscorable)} confirmed date(s) are not in our record and cannot be scored:** "
 f"{', '.join(str(d.date()) for d in unscorable)}. Needs the ERA5 month — "
 f"`docs/karam_handoff.md` Request 1." if unscorable else ""}

## recall@K

{res.to_markdown(index=False)}

`E[hits]` and `p` are computed against the full **{total}**-event set, not only
the dates we happen to hold — otherwise one lucky confirmed date would read as
significance.

## Power against a random ranker

{power_table(N, total).to_markdown(index=False)}

At the literature's own base rate, a random ranker expects **0.016 hits**. Two
hits is p < 0.001. This is why a {total}-event gold set is worth chasing even
though it can never train a model.

## Precision is not computed, deliberately

{gold['location_caveat'].strip()}

## What would make this a real validation

{pending} of {total} dates are still missing, held in:

{chr(10).join(f"- **{b['citation']}** — {b.get('doi') or b.get('journal')} — {b['holds']}" for b in gold['dates_pending']['blocked_on'])}

`docs/karam_handoff.md` Request 0. A screenshot of the event table is enough.
""")


if __name__ == "__main__":
    main()
