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

- [x] Pick one real lead-hour row from `/forecast/latest`'s `catchment_rainfall` array and
      push it through the full chain by hand. Confirm it returns a normal response, not a
      500 or a silently-empty one.
- [ ] The result will sit in "minimal" band regardless — that's Abd's plume-stub ceiling,
      not something your chain is doing wrong. Don't spend time chasing a bigger number;
      confirm correctness, not magnitude.
- [ ] Label the UI-facing output as "latest cached run, issued `<time>`" — same as Phase
      3's requirement. If the timestamp shown is 2026-08-03 while the demo runs on a later
      date, that gap should read as honest, not stale. Say so explicitly if Ali needs a
      "cache age" indicator.

> **Finding, 7 Aug, from Nizar — this is bigger than "confirm it's clean," and both halves
> checked out individually, but they don't connect.** Live-tested against a rebuilt
> container (the 6 Aug audit's "plume-stub ceiling" framing is stale too — Abd's real
> particle engine landed in `0de8c26` and is live: `model_versions.particle_engine` came
> back `custom_2d-calibrated-AQ-2016-10-28`, not a stub):
>
> - `GET /forecast/latest` → `AQ-C01`, `lead_hours=3`, `rain_mm=0.0` — real row.
> - `POST /runoff/predict {"catchment_id":"AQ-C01","rainfall_mm_3h":0.0}` → **200**, real
>   model (`runoff_weighted_gbm_482c7f9_...`), `is_stub:false`.
> - `POST /exposure/calculate {"event_id":"AQ-2016-10-28","outlet_id":"AQ-O01",...}` →
>   **200**, real particle engine, real Allen Coral Atlas zones, honest `results: []`
>   ("No reef zone is reached from AQ-O01 within 24 h" — a genuine not-reached finding,
>   not a fabricated zero).
>
> Both calls are individually clean. **But they are not the same chain** — `ExposureRequest`
> (`schemas.py:319-326`) has no rainfall field at all: `event_id, outlet_id, catchment_id,
> horizon_hours, reef_zone_ids`. There is no way, even by hand, to feed a forecast's
> `rain_mm` into `/exposure/calculate` — it always sources sediment intensity from
> `da.training_row(event_id, cid)` (the historical feature row for `AQ-2016-10-28`) or a
> hardcoded `30.0mm/3h` stub fallback (`main.py` lines ~940-994), never from
> `/forecast/latest`. So "Live Forecast Mode" today means: the cache is real, `/runoff/
> predict` on a forecast row is real, but a forecast lead-hour has **zero path** into an
> exposure score. That's a genuine architecture gap, not a bug in my stream — whoever owns
> `exposure_calculate()`'s sediment-intensity selection (this is Mahdi's/Karam's
> sediment-anchor code) needs to decide whether forecast mode should add a rainfall
> parameter to `ExposureRequest`, or take a different path entirely. Not mine to redesign
> unilaterally this late — flagging for the team to decide.
>
> Also: **the "issued `<time>`" ask is satisfiable today** — `/forecast/latest`'s
> `issued_at` block already carries it (`{"gfs": "2026-08-03T00:00:00+00:00", "gefs":
> "2026-08-03T00:00:00+00:00"}`). What's missing is the frontend: `frontend/src/**` has
> zero references to `/forecast/latest`, and `Mode` includes `'forecast'` but its own i18n
> string is literally `"no live forcing wired yet"`. Ali needs to wire the UI to the
> already-real backend field — not something for me to build, per the ownership table.

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

- [x] Check `exposure/engine.py`'s call site for `confidence_adjustment`. If it's a
      literal `0.6`, that's the real gap — replace it with a value derived from your
      ensemble spread (e.g. `members_exceeding / members_total`).
- [x] Coordinate with Karam on the other half: he owns the exceedance *threshold* your
      spread gets compared against. Neither number means anything without the other.
- [x] Once real, expose the components — `members_exceeding`, `members_total`,
      `threshold_value` — not a single pre-composed sentence. This was Day-1 ask #6 from
      the original frontend contract (`docs/OPEN-ISSUES.md` #4) for exactly this reason: a
      sentence can't be translated cleanly, components can.

> **Confirmed, 7 Aug, from Nizar.** Karam's formula (`main.py`'s `exposure_calculate()`)
> is already live and correct — this was code, not just a proposal, by the time I checked.
> Live-verified against `AQ-O05`/`AQ-C05`: `0/30 GEFS members exceed the 2.34 mm/24h
> threshold -> agreement 1.00, x0.8` — `confidence_members_exceeding: 0,
> confidence_members_total: 30, confidence_threshold_value_mm: 2.3406,
> confidence_adjustment: 0.8`. All three components are on `formula_terms`, not a
> sentence, per the ask. "Confidence" meaning ensemble agreement (capped by the
> currents/bathymetry penalty) is the right reading — see the dated comment now in
> `main.py` itself, right above the formula. No code change needed; signed off as-is.

---

## 3 · Multi-Source Weather Agreement (feature F) — 🟡 same threshold gap, different pair

This is the GFS-vs-GEFS (or HYCOM-vs-Copernicus, if the intended comparison is currents
rather than rainfall — confirm which one the feature actually means before building) case
of item 2's problem: an "agreement" score is only honest once the threshold defining
agreement is real.

- [x] Confirm which comparison this feature is actually asking for. If it's currents, you
      already have the artifact — `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`
      is a real, already-generated comparison from `047b985`. That's demoable **today** as
      a static exhibit; it does not need live re-running for the demo unless someone wants
      a fresh event window.
- [x] If it's rainfall-model agreement (GFS vs GEFS), that's a new comparison, not an
      existing one — check `/forecast/latest`'s two model blocks before assuming it's
      already computed.
- [x] Either way, don't invent a new "agreement" threshold independent of the one you and
      Karam settle on in item 2 — one honest number, reused, beats two similar-looking ones
      that quietly disagree.

> **Done, 7 Aug, from Nizar.** Full decision + resolution written up in
> `tasks/phase4/00-phase4-plan.md`'s Feature F row. Built the currents reading as a live
> endpoint, `GET /api/v1/currents/agreement` — not just the static screenshot — since a
> live-queryable number beats a fixed image for anything Ali's UI wants to show.
> Live-verified: matches the documented 65.8° historical disagreement exactly, and the
> "today" variant honestly returns `null` (not a crash, not a fabricated number) when the
> live cache has aged past its fetch window — a real gap, correctly reported as one.

---

## 4 · Re-verify your own Phase 3 persistence

Not a new feature — a request to close the gap the audit couldn't check.

- [x] Confirm `model_versions`, `reef_exposures`, `runoff_predictions` in Supabase
      actually hold rows matching what's on disk right now (the real trained artefact, the
      non-zero exposure runs from the sediment anchor landing). If they were populated
      before sediment anchoring merged, they may be stale relative to today's real numbers.
- [x] If the demo reads from Supabase rather than the local SQLite store for any of these,
      say so to Pulga explicitly — his exposure store writes local SQLite by design, and a
      demo pointed at a stale Supabase mirror instead would show old zeros next to a live
      API showing real numbers.

> **Done, 7 Aug, from Nizar.** Confirmed stale exactly as suspected: Postgres
> `model_versions` held only the pre-sediment-anchor artifact (`2194b48`), missing the
> two retrains that actually fixed the bug. Refreshed: re-ran `model_versions.py`
> (now 3 rows) and `exposure_runs.py` after seeding 5 fresh per-outlet runs against the
> live container (`scripts/seed_demo_exposure_run.py`'s logic, run via real HTTP calls
> since the API image has no `httpx` for the script's own `TestClient` — same effect,
> same DB file) — `simulation_runs`/`reef_exposures` now correctly show
> `plume_source: REAL_PARTICLE_ENGINE` and the current model version. Found and fixed
> two real bugs along the way: (1) the bridge loader's `engine` label only knew about
> `SYNTHETIC_STUB`, so real-particle-engine runs were mislabeled `unknown` — fixed; (2)
> `backend/src/db/client.py`'s shared engine hit
> `psycopg.errors.DuplicatePreparedStatement` on repeat writes against Supabase's
> transaction-mode pooler — fixed with `connect_args={"prepare_threshold": None}`, which
> benefits every future loader, not just this one. **The bigger finding, written up in
> `tasks/phase4/04-pulga.md`:** the live demo path never touches Postgres, by design —
> Postgres is a batch mirror only. `runoff_predictions` stays unpopulated; nothing writes
> to it anywhere in the current codebase (not my Phase 3 scope, and not silently added
> here).

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
