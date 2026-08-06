# Nizar — Phase 4

> **Update, 6 Aug, from Karam — item 2's threshold half is done, needs your sign-off.**
> `confidence_adjustment` was a literal `0.6`; it's now derived from
> `da.gefs_exceedance_for(catchment_id)` (your `forecast_exceedance` snapshot data) via
> `agreement = |exceedance_prob − 0.5| × 2`. **This mapping is a proposal, not settled —
> confirm or correct it**; you own whether "confidence" should mean ensemble agreement
> at all. The accessor and call site (`backend/src/api/data_access.py`'s
> `gefs_exceedance_for`, `main.py`'s `exposure_calculate()`) are both small if it needs
> to change. Components (`confidence_members_exceeding/_total/_threshold_value_mm`) are
> now on `formula_terms`, not just a sentence, per your own item 2 ask.
>
> **Also ran your item 4 (Supabase re-verification) — got credentials working, here's
> what's actually there.** `events`/`catchments`/`reef_zones`/`outlets`: zero orphans,
> zero mismatches, all 675/5/8/5 rows match the on-disk parquet/gpkg exactly (checked
> row-by-row, not just counts — e.g. the demo event's `rank: 13` in
> `source_references` matches today's real value). That side is clean.
>
> **`model_versions` and `reef_exposures` ARE stale, confirmed, not just suspected.**
> `model_versions` has exactly one row: `runoff_weighted_gbm_2194b48_...` (trained Aug 3)
> — the currently-serving model is `runoff_weighted_gbm_482c7f9_...` (Aug 5, after the
> sediment-anchor merge). Two newer versions never got registered. `reef_exposures` has
> exactly one row, `confidence: 0.6` — the literal I just replaced — from a run before
> today's fix. `runoff_predictions` is empty, 0 rows.
>
> **The demo does not write to Supabase at all** — confirmed, not inferred: I ran dozens
> of `/exposure/calculate` calls against the live container throughout this whole phase
> (verifying the confidence fix, the events catalogue, etc.) and none of them added a row
> here. `exposure.store` writes local SQLite by design (its own docstring says why). If
> the demo or a judge-facing view ever reads exposure/model history from Supabase instead
> of the API/SQLite, it will show Aug 3 numbers next to a live API showing Aug 6 ones —
> exactly the mismatch your file's item 4 was worried about. Either wire the live path to
> also register in Supabase, or make sure nothing demo-facing reads from these three
> tables. (Credentials: pooler URL now in `backend/.env`, gitignored, not committed —
> the direct `db.<ref>.supabase.co` host is IPv6-only here and just hangs.)

Read [`00-phase4-plan.md`](00-phase4-plan.md) first.

`/api/v1/forecast/latest` is real and live — I called it during the audit: GFS (1 member)
+ GEFS (30 members), cached snapshot dated 2026-08-03, real per-catchment rain/wind at
every lead hour to 48h. That was the Phase 3 ask and it shipped. Phase 4 is about what
that cached forecast actually *drives* once it's inside the risk chain, and one thing I
could not verify this round — say so up front so nobody assumes I checked it.

**I did not verify Supabase this time.** The containers I ran had no `.env` and no
Supabase credentials configured — the worker logged `SUPABASE_URL unset — idling` the
whole session. If your Phase 3 persistence work (`model_versions`, `reef_exposures`,
`runoff_predictions` tables) depends on a live Supabase connection, none of that was
exercised in this audit. Re-verify it yourself; don't take "the audit didn't flag it" as
"the audit confirmed it."

---

## 1 · Live Forecast Mode (feature 2) — 🟡 the chain, not the cache

The cache itself is done and good. What's unconfirmed is whether feeding a cached
forecast timestep all the way through `/runoff/predict` → `/exposure/calculate` actually
produces a clean result end to end, rather than erroring on a missing field the historical
demo-event path doesn't need.

- [ ] Pick one real lead-hour row from `/forecast/latest`'s `catchment_rainfall` array and
      push it through the full chain by hand. Confirm it returns a normal response, not a
      500 or a silently-empty one.
- [ ] The result will sit in "minimal" band regardless — that's Abd's plume-stub ceiling,
      not something your chain is doing wrong. Don't spend time chasing a bigger number;
      confirm correctness, not magnitude.
- [ ] Label the UI-facing output as "latest cached run, issued `<time>`" — same as Phase
      3's requirement. If the timestamp shown is 2026-08-03 while the demo runs on a later
      date, that gap should read as honest, not stale. Say so explicitly if Ali needs a
      "cache age" indicator.

---

## 2 · Confidence Meter — the ensemble half (feature 5) — 🟡 a real, specific finding

I pulled a live `formula_terms` during the audit:

```
confidence_adjustment: 0.6
confidence_adjustment_reason: "coarse global current model + GMRT-substituted bathymetry"
```

**That reason string reads like a fixed constant, not something computed from your
30-member GEFS spread.** I can't be certain from the outside — it's possible 0.6 is what
the real spread happened to produce for this exact request — but the reason text doesn't
mention spread at all, and a genuinely computed confidence should cite the number of
members exceeding some threshold, the way `runoff_model.py`'s own `confidence_terms`
field already does (`catchment_ap`, `missing_fraction`, etc.).

- [ ] Check `exposure/engine.py`'s call site for `confidence_adjustment`. If it's a
      literal `0.6`, that's the real gap — replace it with a value derived from your
      ensemble spread (e.g. `members_exceeding / members_total`).
- [ ] Coordinate with Karam on the other half: he owns the exceedance *threshold* your
      spread gets compared against. Neither number means anything without the other.
- [ ] Once real, expose the components — `members_exceeding`, `members_total`,
      `threshold_value` — not a single pre-composed sentence. This was Day-1 ask #6 from
      the original frontend contract (`docs/OPEN-ISSUES.md` #4) for exactly this reason: a
      sentence can't be translated cleanly, components can.

---

## 3 · Multi-Source Weather Agreement (feature F) — 🟡 same threshold gap, different pair

This is the GFS-vs-GEFS (or HYCOM-vs-Copernicus, if the intended comparison is currents
rather than rainfall — confirm which one the feature actually means before building) case
of item 2's problem: an "agreement" score is only honest once the threshold defining
agreement is real.

- [ ] Confirm which comparison this feature is actually asking for. If it's currents, you
      already have the artifact — `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`
      is a real, already-generated comparison from `047b985`. That's demoable **today** as
      a static exhibit; it does not need live re-running for the demo unless someone wants
      a fresh event window.
- [ ] If it's rainfall-model agreement (GFS vs GEFS), that's a new comparison, not an
      existing one — check `/forecast/latest`'s two model blocks before assuming it's
      already computed.
- [ ] Either way, don't invent a new "agreement" threshold independent of the one you and
      Karam settle on in item 2 — one honest number, reused, beats two similar-looking ones
      that quietly disagree.

---

## 4 · Re-verify your own Phase 3 persistence

Not a new feature — a request to close the gap the audit couldn't check.

- [ ] Confirm `model_versions`, `reef_exposures`, `runoff_predictions` in Supabase
      actually hold rows matching what's on disk right now (the real trained artefact, the
      non-zero exposure runs from the sediment anchor landing). If they were populated
      before sediment anchoring merged, they may be stale relative to today's real numbers.
- [ ] If the demo reads from Supabase rather than the local SQLite store for any of these,
      say so to Pulga explicitly — his exposure store writes local SQLite by design, and a
      demo pointed at a stale Supabase mirror instead would show old zeros next to a live
      API showing real numbers.

---

## Definition of done

1. One cached-forecast row run through the full chain by hand, confirmed clean.
2. `confidence_adjustment` confirmed derived from real GEFS spread, or fixed if it isn't.
3. Confidence components exposed (not a pre-composed sentence).
4. Multi-Source Weather Agreement's actual comparison identified and either backed by the
   existing currents screenshot or built fresh.
5. Supabase tables re-verified against current disk state, staleness called out if found.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | the exceedance threshold half of confidence | Partial — you can wire the ensemble half now |
| **Pulga** | which store (SQLite vs Supabase) the demo actually reads | No — ask now, before building on an assumption |
