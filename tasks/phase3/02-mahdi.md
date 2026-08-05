# Mahdi — Phase 3

**You hold the one task that gates five others.** Read [`00-phase3-plan.md`](00-phase3-plan.md)
first if you have not.

Your Component A work is done and it is good: 11,810 rows, LOCO AP **0.741** against a
rule baseline of **0.200**, two leaks found and removed, and the leakage check I asked for
came back at random-CV 0.514 vs LOCO 0.521 — a gap of −0.008, so the model is not
memorising catchment identity. That result stands.

This phase is not about improving it.

---

## 1 · Anchor the sediment proxy — 🔴 do this first, alone

**Every reef zone in the product currently reads `minimal` risk, and this is why.**

Exposure is a product of five terms. Measured against the live API on 4 Aug:

```
plume_probability            0.603
relative_sediment_intensity  0.000   ← yours
exposure_duration_weight     0.500
habitat_sensitivity_weight   1.000
confidence_adjustment        0.600
─────────────────────────────────────
risk_score                   0.0     risk_level: minimal
```

The plume genuinely reaches **41 % of R-01 within 12–24 h**. The card still says minimal.
One zero zeroes the product.

Your own code states the fix. `sediment_basis` returns:

> `UNANCHORED - index is comparable between requests, but no absolute class exists.`
> `Anchor the proxy at training time on AQ-2016-10-28 / AQ-C01 (~24,400 t).`

- [ ] Anchor it. **One documented number**, from the literature, for one event and one
      catchment.
- [ ] Keep `sediment_basis` honest afterwards — it should say what it is anchored to, not
      drop the caveat. An anchored index is still an index.
- [ ] Confirm `sediment_class` comes back non-null so the map can colour zones by risk.

**Watch out — the vocabulary.** `sediment_class` crosses three modules and they disagreed
until 4 Aug: your proxy emitted `"Medium"`, the particle engine keys on `"medium"`, and the
API schema demanded `"moderate"`. Canonical is now lowercase **`low | medium | high |
extreme`**, pinned by `tests/test_sediment_class_vocabulary.py`. `None` is legal and means
"the proxy did not run" — it must not be defaulted to a class.

**This unblocks:** exposure scores, `/alerts`, the dashboard numbers, the what-if sliders,
and the reef colouring on the prediction image. Five things, one number.

> If this has not moved by end of **5 Aug**, Karam takes it. Say so early rather than late
> — that is not a criticism, it is the schedule.

---

## 2 · Point the exposure engine at your real model

The engine is calling your **stub**, not your artefact. From the stored `formula_terms`:

```
relative_sediment_intensity_source : "runoff stub for AQ-C01 at 30 mm/3h"
model_versions.runoff_model        : "stub-0.1"
```

Meanwhile `/api/v1/models` serves
`runoff_weighted_gbm_2194b48_20260803T214757Z` quite happily.

- [ ] Make the exposure path call the registered artefact.
- [ ] `model_versions` in every stored run must name the real version, so a score is
      reconstructable six hours later.

**Watch out — I fixed the key mismatch on the API side on 4 Aug, and it is worth knowing
what it was.** The handler read `predicted_runoff_m3`, `model_version` and
`relative_sediment_intensity`; your `predict_one` returns none of those three. Every one
failed *softly*: the volume defaulted to **0.0** so a real prediction rendered as
"0 m³ of runoff", and the version fell back to a string that made the provenance line read
"Mahdi's runoff model **None**". The keys are `model_version_id`, `runoff_probability` and
`sediment_index`. `predicted_runoff_m3` is now `None` on purpose — Component A predicts
occurrence, not volume, and a fabricated zero carrying a model's authority is the one thing
this project must not ship.

---

## 3 · AQ-C01 — the fold that matters most

It is your weakest at **0.593** and it carries **96 % of the discharge**. Every alert that
matters comes out of Wadi Yutum.

- [ ] Whatever you were doing here — the classifier/regressor ensemble — is the right call.
- [ ] Report it per fold, not just the mean. A mean of 0.741 that hides 0.593 on the only
      catchment that matters is a worse result than it looks.

**Do not chase the mean.** You measured run-to-run variance at **±0.017 AP** from column
ordering alone, so anything under ~0.03 cannot be distinguished from noise on five folds.
Spend the time on AQ-C01 or on the model card, not on a delta you cannot defend.

---

## 4 · Rebuild with `rain_3h_mm` when it lands

Your Request 2, and you called it correctly: the model trains on daily totals, and in a
hyper-arid catchment intensity generates runoff, not depth. 6 mm in an hour and 6 mm over
twelve hours are currently **identical** to it.

The sweep is running — 33,920 of 97,200 granules on 4 Aug, **wettest storms first**, so
every day above 1 mm lands early.

- [ ] When Karam says the matrix is rebuilt, retrain and report the delta honestly. If
      intensity does not help, that is a finding worth writing down.

---

## 5 · Docker — you were further along than the task list implied

I tested it on 4 Aug: image builds, container healthy in ~8 s, worker starts behind it.
Two targets from one base, deps layered before code, non-root, healthcheck, frontend behind
a Compose profile so `up` works before Ali's directory exists. That was careful work and I
flagged it as a risk before I had checked. It was not.

Three things changed underneath it that you should know about:

- `requirements-api.txt` gained the **vector geospatial stack** plus matplotlib/pillow.
  `exposure/engine.py` imports geopandas at module scope and the container could not start
  without it. rasterio and whitebox stay in the worker.
- The api target now creates `/app/var` and chowns it. A named volume inherits the image's
  ownership at the mount point; without that, sqlite failed on a mount that looked fine.
- Host ports are overridable — `API_PORT=8100 docker compose up`. A hard-coded 8000 makes
  `up` fail outright when anything else holds it, and DoD item 6 is judged on a laptop
  nobody controls.

- [ ] **`docker compose up` on a clean clone with the wifi off**, at least twice before the
      12th. That is item 6 and nobody can substitute for you on it at the last minute.
- [ ] `data/` is a bind mount, not baked in, and it is git-ignored. Decide before the 12th:
      bake the demo subset into the image, or ship a documented volume.

---

## Definition of done

1. **Sediment proxy anchored**, documented, and `sediment_class` non-null.
2. Exposure calls the real artefact; `model_versions` names it.
3. Per-fold results reported, AQ-C01 called out explicitly.
4. Model card: target definition, threshold, LOCO **and** temporal holdout, the rule
   baseline's own score, and the ±0.017 noise floor.
5. `docker compose up` works twice from a clean clone with wifi off.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | `rain_3h_mm` in the matrix | No — anchor sediment first, it needs nothing |
| **Nizar** | Supabase for `model_versions` | Only for the write, not for training |
| Nobody | the sediment anchor | **It is one number from the literature** |
