# Pulga — Phase 4

Read [`00-phase4-plan.md`](00-phase4-plan.md) first.

Everything from Phase 3 held up under live testing on 6 Aug: `/alerts` returns real
stored runs, `/explain` and `/ask` both verified against the running container,
`position_confidence` and the `Value` wrapper fixes are in and tested, and the exposure
engine now produces genuinely non-zero scores now that sediment is anchored. Nothing here
is a bug in what you already shipped. It's four small, well-scoped additions, each one
either a thin read-through or a bounded new request field — no redesign.

---

## 1 · What-If Scenario Presets + Judge-Controlled Slider (features 7 & 15) — 🔴 the biggest ask this phase

Same root cause, same fix. `ScenarioDrawer.tsx` already exists on the frontend with six
controls, and its own i18n copy says outright: *"these controls move a transparent index,
not a calibrated model."* That was the right call while sediment was 0.0 — a slider
moving a placeholder invites "what is that based on?" Sediment is anchored now, so the
honest thing to do is either wire the drawer to something real, or leave the copy as-is
and say clearly this phase didn't get to it. Don't let the UI silently start implying a
real recompute while still carrying "not a calibrated model" as its caption.

- [ ] Add an optional rainfall multiplier to `RunoffRequest` (and thread it through to
      `ExposureRequest` if the exposure route needs to re-derive runoff rather than reuse a
      stored prediction). Bounded, not open range — Mahdi's file has the valid range for
      `transmission_loss`; get the equivalent sane bounds for a rainfall multiplier before
      shipping an endpoint that accepts anything.
- [ ] Route it through `predict_one()` with the scaled `rainfall_mm_3h`, same pattern
      `main.py`'s existing runoff route already uses for the real-artefact path.
- [ ] Confirm the response still carries `formula_terms` showing which term moved and by
      how much — that's what makes the slider explain itself instead of just producing a
      different number.
- [ ] Tell Ali once this is live so `ScenarioDrawer` can point at
      `POST /api/v1/exposure/calculate` instead of a local index, and so the "not a
      calibrated model" copy gets updated to match reality — don't leave stale disclaimer
      text next to a now-real control.

---

## 2 · Real Sensor Proof Overlay (feature 10) — 🔴 a thin read-through, not new work

`data/processed/marine/mooring_target_AQ-2016-10-28.json` is real, complete, and
per-field provenance-tagged (reported vs. derived vs. timezone-converted) — Abd's
derivation work here is already done and file-cited. The gap is entirely that **no
endpoint serves it.** I grepped the whole API tree during the audit; it appears only
inside prose caveat strings, never as structured data.

- [ ] Add `GET /api/v1/events/{event_id}/mooring` (or fold it into the existing
      `/events/{event_id}` response as an optional field) that reads the file straight
      through — this is closer to how `da.events()` already parses `docs/event_dates.md`
      than to any of the geometry loaders; no GeoDataFrame involved.
- [ ] Keep every provenance tag from the source file intact in the response. The whole
      point of this overlay is "here's what we predicted, here's what a real sensor
      measured" — if the derived-vs-reported distinction gets flattened on the way out,
      the overlay loses the thing that makes it a *proof* rather than a claim.
- [ ] Coordinate with Abd on which fields the overlay UI actually needs (turbidity peak,
      salinity anomaly, elevated-duration window) — don't expose the whole file blind if
      only three numbers are going on screen.

---

## 3 · Wire real SHAP drivers into `/explain` (feature 4) — 🟡 waiting on Mahdi's confirmation

`ExplainRequest.shap_drivers` already accepts a list of `{feature, value, contribution}`
dicts and `DriverBars.tsx` already renders them — this has been wired end to end since
Phase 3, just fed by hand-typed examples in every test so far. Mahdi's file has him
confirming `predict_one()`'s `feature_attributions` field is populated from a real feature
row, not a synthetic one.

- [ ] Once he confirms it, thread `feature_attributions` from `predict_one()`'s output
      straight into the `shap_drivers` field the explain route already accepts — this
      should be a small change at the call site in `main.py`, not new plumbing.
- [ ] Re-run `tests/test_explain_fidelity.py` and the adversarial explain tests after —
      real SHAP values will have different magnitudes/signs than the hand-typed fixtures,
      and the number-fidelity checker should still pass without modification if the wiring
      is clean.

---

## 4 · Expose `transmission_loss` as a bounded parameter (feature C) — 🟡 waiting on Mahdi's range

`predict_one()` already returns a real `transmission_loss` value (0.525 on the request I
tested live) — the parameter exists today, it's just not adjustable from outside the
model. Mahdi's file has him documenting its valid range and what it means physically.

- [ ] Once he hands you the range, add it as a bounded, optional field on whichever
      request the slider will call — same shape as the rainfall multiplier in item 1, and
      ideally added in the same pass so Ali isn't wiring two near-identical controls on two
      different schedules.
- [ ] Make sure the response echoes back the value actually used (not just accepts it
      silently) — Ali needs to show the slider's current position reflects what the model
      actually computed with, not just what was requested.

---

## 5 · Small joins for Ali — reef zone priority, dive sites, coastal comparison (features A, B, I)

Three different frontend views, same underlying need: a way to get exposure scores keyed
by reef zone without the client re-deriving anything.

- [ ] Confirm whether `/api/v1/alerts` (sorted by risk already, since it filters by
      `min_level`) is sufficient for the "named reef zone priority list" (A) and "coastal
      zone comparison" (I) views, or whether Ali needs a dedicated
      `GET /api/v1/exposure/summary` that returns one row per zone without the alert
      framing. Don't build a new endpoint if the existing one already answers the
      question — check with Ali what shape he actually needs first.
- [ ] For dive-site safety status (B): once Karam hands you the confirmed `places.geojson`
      POI shape, write the nearest-reef-zone join. This is server-side because it needs
      live exposure scores, which only exist behind the API — don't let this drift into a
      frontend-side turf.js join against stale fixture data.

---

## 6 · Verify what's already ✅ still holds

Six rows in the plan are marked done. Before anyone treats them as settled:

- [ ] Bilingual Assistant (6): re-run `tests/test_ask_citations.py` and
      `tests/test_explain_ask_adversarial.py` after this phase's other backend changes
      land — nothing here should touch RAG, but "should" isn't "confirmed."
- [ ] Click-to-See-Why (12) and Enclosed Harbor Warning Flag (E): both already real in
      `formula_terms` and `cav.harbour_outlet()` respectively — no action needed unless
      Ali reports the UI isn't finding the fields it expects.

---

## Definition of done

1. Rainfall multiplier live on a real endpoint, `formula_terms` shows the effect, Ali
   notified to repoint the drawer.
2. Mooring data reachable via a real endpoint, provenance tags intact.
3. Real SHAP drivers flowing into `/explain`, fidelity tests still green.
4. `transmission_loss` exposed as a bounded, echoed-back parameter.
5. Reef-zone joins for A/B/I resolved — either the existing `/alerts` shape is confirmed
   sufficient, or the one new summary endpoint is built.
6. All six already-✅ rows re-confirmed live after this phase's changes, not assumed.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | `feature_attributions` confirmed real, `transmission_loss` bounds | Yes for items 3 and 4, no for item 1 |
| **Abd** | which mooring fields the overlay needs | No — build the read-through now, narrow the fields with him after |
| **Karam** | confirmed dive-site POI shape | Yes for the join in item 5 |
