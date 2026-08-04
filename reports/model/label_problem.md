# The label is not the thing we named it

**Date:** 4 August 2026 · Mahdi · supersedes the falsification verdict in
`reports/model/sediment_anchor.md`

Component A's target is called `target` and described everywhere as *"will runoff
reach the sea."* It is not that. It is **"did ERA5-Land generate surface runoff,"**
and those two statements differ by a factor of about twenty.

This was found while trying to fix Component B, and it explains that failure
rather than being a separate problem. Three independent measurements say the same
thing.

---

## 1 · The label is a near-deterministic function of ERA5's own rainfall

| correlation | r |
|---|---:|
| `sro` vs **ERA5** rainfall | **+0.985** |
| `sro` vs **IMERG** rainfall | +0.564 |
| ERA5 rainfall vs IMERG rainfall | +0.573 |

ERA5-Land's runoff is computed by ERA5-Land's own land-surface scheme from
ERA5-Land's own precipitation. At r = 0.985 the label carries almost no
information that its own forcing does not already carry.

So a model predicting `sro` from rainfall features is substantially recovering
**ERA5's internal rainfall→runoff mapping**, not the physical response of these
wadis. Where the features come from IMERG and the label from ERA5, part of the
0.741 AP is the model learning the ERA5↔IMERG offset — the two products agree
only at r = 0.573, and ERA5 runs at a median **0.43×** IMERG on wet days.

## 2 · ERA5 largely missed the one event we can verify

| | ERA5 rain | ERA5 peak 3 h | IMERG rain | percentile |
|---|---:|---:|---:|---|
| 2010-01-18 | 31.0 mm | 14.7 mm | 17.5 mm | ERA5 p99.9 |
| **2016-10-27** | **0.77 mm** | **0.32 mm** | **9.58 mm** | ERA5 p92.6 / IMERG **p99.5** |

October 2016 is the flood with a mooring record, 24,400 t of sediment and a
published paper. In ERA5 it is an unremarkable damp day.

This is why `scripts/20_sediment_anchor_and_rank.py` ranked it 193 of 2,362 and
why `scripts/21_extract_intensity.py` did not rescue it. **Both scripts were
testing the sediment formula against a label that had not seen the storm.** The
formula was never what failed; the ranking test was invalid as constructed.

## 3 · The base rate is off by 21×

Kalman et al. (2025) state plainly that the 28 October 2016 flood was **"the 13th
flood recorded since records began in 1994"** — 0.17 floods/yr through the
1994–2012 drought, 1.7/yr for 2012–2020, and *"the likelihood of floods occurring
in a given day in the year is less than 0.5%."*

| | events | per year | share of calendar days |
|---|---:|---:|---:|
| Our `target` fires | 288 days | 11.7 | 3.21% |
| Documented sea-reaching floods | 13 | 0.57 | 0.156% |

Some of that gap is legitimate — we count five catchments where the literature
counts one canal, and "runoff generated somewhere upstream" is a weaker event than
"water arrived at the shoreline." But a **21× discrepancy is not a definitional
detail.** It is the signature of a label that fires on ordinary wet days.

Note the direction this cuts: our label is *too generous*, so Component A's 7.9%
prevalence is not the hard-imbalance problem we spent the modelling effort on. The
real phenomenon is roughly **0.16% of days**, twenty times rarer than anything we
have trained against.

---

## What the right label is, and what it would cost

The label should be **"did sediment reach the sea."** The good news is that this
is not n = 1. The literature documents **13 such events, 1994 to October 2016**,
with the modern rate implying a handful more through 2020.

The bad news is that **we have the count but not the dates.** They are in two
papers not on disk:

| source | what it holds | identifier |
|---|---|---|
| Kalman et al. 2020b | the 1994– flood record behind the 0.17/yr and 1.7/yr rates | *Sedimentology* 67, 3152–3166 · `10.1111/sed.12737` |
| Katz et al. 2015 | the earlier hyperpycnal plume event, ≈20,000 t | cited as Katz et al., 2015a/b |

Thirteen dated events across five catchments is still far too few to train a
supervised classifier — but it is **enough to validate one**, which is a different
and achievable claim. That makes chasing these two citations the highest-value
data request open on the project.

## What this means for each component

**Component A** keeps its metrics but must change its stated claim. It predicts
ERA5-Land surface-runoff generation with LOCO AP 0.741, and that is a defensible,
reproducible result. It does **not** predict whether runoff reaches the sea, and
the model card must say so.

**Component B** stays a formula: `k` anchored on one published mass, `τ` reported
as the 20–85% Negev band. Nothing about it is trained. The ranking test is retired
— not because it was too strict, but because it scored the formula against an ERA5
label that missed the anchor event.

**The mooring record** — peak suspended sediment 2.18 g/L, 31.42 h elevated,
salinity anomaly 19σ — is a **validation target, not a training label.** One
event cannot supervise six terms. This was always the design intent; the label
audit just makes the reason explicit.

## Incidental corroboration of the hydrology

The same paper independently confirms two Phase 1 results. It gives Wadi Yutum as
**4,867 km²** against our delineated exorheic **4,453 km²** and HydroBASINS'
**4,690 km²** — three methods within 9%, though the paper does not say whether its
figure includes the northern sinks. And it notes Yutum *"possesses several sinks
and sabkhas in the north, but rainstorms in the rocky southern slopes send water
towards Aqaba"* — which is precisely the behaviour
`scripts/10_endorheic_mask.py` was built to capture, arrived at from the DEM
alone.
