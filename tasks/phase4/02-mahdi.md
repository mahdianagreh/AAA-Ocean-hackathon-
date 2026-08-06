# Mahdi — Phase 4

Read [`00-phase4-plan.md`](00-phase4-plan.md) first.

Sediment is anchored now — real, live, non-zero, verified against the running API on
6 Aug: `relative_sediment_intensity: 0.084`, provenance string reading
`"sediment_index 13,313 = 0.09x AQ-2016-10-28..."`, `model_versions.runoff_model` naming
your real artefact instead of `stub-0.1`. That was the single gate on five things in
Phase 3 and it's closed. This phase is five smaller, more specific asks, and one of them
is a warning label on your own work, not a bug.

---

## 1 · Top Weather Drivers Explainer (feature 4) — 🟡 probably closer than the audit could tell

I called `predict_one()` directly during the audit and it already returns
`feature_attributions` — real SHAP values, e.g. `temp_c: -1.81`, `wind_direction_deg:
-1.10`, `rain_self_percentile: 0.78`. That's not nothing; the audit flagged this row
"needs confirming" because it couldn't tell from the outside whether that field actually
reaches a live response consistently, or what `feature_attributions_status` (I saw it
come back `None`) is supposed to signal.

- [ ] Confirm `feature_attributions` is populated for a real feature row (via
      `da.training_row()`), not just for the minimal/synthetic request I happened to test
      with — a request missing 19 of 20 features produces SHAP values too, but they're not
      the ones worth explaining.
- [ ] Document what `feature_attributions_status` means and when it's non-`None`. If
      nobody can answer that in one sentence, the field is either dead code or an
      unfinished thought — resolve one way or the other before Ali builds against it.
- [ ] Hand Pulga the confirmed shape so `/explain`'s `shap_drivers` input can be populated
      from real attributions instead of a hand-typed example. `DriverBars.tsx` already
      exists on the frontend — this is the last real gap before it shows real numbers.

---

## 2 · "The AI Never Saw This Storm" (feature 9) — 🟡 one number, and it doesn't exist yet

I searched every report and the registered model's metrics ledger. LOCO (0.7474) is real
and reportable today. **A standalone train≤2014/test≥2015 AP does not exist anywhere** —
not in `reports/`, not in `model_versions.jsonl`. The only temporal split that's actually
implemented is the calibration slice (latest 25% by date), and that's a different claim:
it says the calibrator hasn't seen the test rows, not that the classifier has never seen
2016.

- [ ] Compute it. Split `training_set_full.parquet` by date at end-of-2014, train on the
      earlier side, score AP on the later side. `scripts/19_train_production_model.py`
      already has the CV scaffolding — this is an adaptation, not new infrastructure.
- [ ] Record it next to `mean_AP` in `model_versions.jsonl["metrics"]`, labelled clearly
      as `temporal_holdout_AP` so nobody confuses it with LOCO again.
- [ ] **Do not ship the feature name before the number exists.** "The AI never saw this
      storm" is a strong, specific, checkable claim — say it only once you can point at a
      metric computed the way the sentence describes.

---

## 3 · Transmission Loss Reality Check (feature C) — 🟡 confirm the range, then let Pulga expose it

`transmission_loss: 0.525` is a real field in `predict_one()`'s output today — the
parameter exists, this part of the audit's "likely exists" guess was right.

- [ ] Document its valid range and what a slider should be allowed to move it between —
      Pulga needs this to build a bounded API parameter, and Ali needs it to build a
      slider that can't be dragged to a physically meaningless value.
- [ ] State in one line what transmission loss *means* physically (soil absorbing runoff
      before it reaches the wadi bed, per the curve-number formula) — this is exactly the
      kind of number that looks like a UI toy unless the caption explains why it moves the
      score.

---

## 4 · Culvert & Drainage Correction Map (feature D) — ✅ your data, just needs rendering

This is already real and already documented: 27 mapped culverts,
`scripts/12_culvert_crosscheck.py`'s cross-check against the routed network, and the
results (`culvert_verdict`, `nearest_culvert_m`, `unmodelled_coastal_culverts`) are
**already exposed on `/api/v1/outlets`** — that shipped in the seam-vocabulary fixes
earlier this project. AQ-O02 and AQ-O03 both carry a live `"CANDIDATE CORRECTION —
unmodelled path to the sea"` verdict right now.

- [ ] Nothing to build on your side. Confirm to Ali that the outlet-level fields are
      the whole story — there's no separate per-culvert endpoint, and if the map needs
      individual culvert points rather than per-outlet summaries, say that now rather than
      after the layer is half-built.

---

## 5 · Post-Storm Damage Estimate (feature J) — 🔴 this one needs your name on the correction, not just the code

This is the one row in the whole list that's risky **as written**, and it's your formula,
so the correction has to come from you and be visible, not quietly implemented.

Your own anchor file says it outright:

> *"ONE measurement fixes the SCALE, never the SHAPE. The formula has six terms and a
> single point constrains one degree of freedom, so any mass for a different event is an
> extrapolation along an unverified curve."*

A feature that reports "**this storm will deposit ~18,200 tonnes**" for anything other
than AQ-2016-10-28 is reporting a number the anchor doesn't support, dressed up as
precision.

- [ ] Confirm the API never emits a tonnage figure for a non-anchor event — only
      `sediment_class` (Low/Medium/High/Extreme) and the relative index. If a tonnage
      figure is reachable anywhere in the response for a different event, that's a bug to
      close, not a feature to ship.
- [ ] Write the one-paragraph version of the anchor caveat above in language a judge
      reads, not a data scientist — hand it to Ali so the UI copy says "relative severity
      class" and never "estimated tonnage" for anything but the anchor event itself.

---

## 6 · Offline Emergency Mode (feature H) — 🟡 you own the physical test

Docker is genuinely solid right now — I brought up all three services live during the
audit (api healthy, worker up, frontend serving 200 on :5173) without touching your
Dockerfile. What's unverified is the literal claim: wifi physically off, not a proxy.

- [ ] Run it for real: wifi off, `docker compose up` (add `--profile frontend` for the
      third view), walk the whole story. This is the same DoD item from Phase 3 — nobody
      else can substitute for you on it at the last minute, because it's your image and
      your compose file.
- [ ] Ali has a Playwright test (`wifi-off.offline.spec.ts`) that mechanises a DNS
      blackhole as a regression guard — that's a good automated proxy for "did this
      regress since last time," but its own docstring says the physical test is still the
      real gate. Run both; trust the physical one.

---

## Definition of done

1. `feature_attributions` confirmed real against a real feature row; `_status` field's
   meaning documented or removed.
2. Temporal holdout AP computed and recorded in `model_versions.jsonl`.
3. `transmission_loss`'s valid range documented for Pulga and Ali.
4. Culvert fields confirmed sufficient for Ali's map layer — no new endpoint needed.
5. No tonnage figure reachable for a non-anchor event; the honest-framing paragraph
   written for Ali.
6. `docker compose up` (with the frontend profile) run with wifi physically off, at
   least once.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nobody** | items 2, 3, 5, 6 | No — all four are yours alone |
| **Pulga** | wiring `feature_attributions` into `/explain` | No — confirm your shape first, he builds after |
