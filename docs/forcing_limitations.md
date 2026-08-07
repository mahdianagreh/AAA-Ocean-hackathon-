# Forcing Limitation — Ocean Current Resolution

**Owner:** Nizar. Read this before answering any judge question about plume accuracy.

## The one-paragraph statement (read this off the slide)

> The best free global ocean current models — Copernicus Marine and HYCOM — run at
> roughly 1/12 degree, about 9 km per grid cell. The Gulf of Aqaba is only 15–25 km wide.
> That means the entire gulf is spanned by two or three grid cells, so the nearshore
> circulation — precisely where the reefs are — is not resolved. We saw this directly: our
> own provisional wadi outlet coordinate lands on a grid cell the model treats as masked
> land, not water. This is exactly why ReefShield does not output a single plume
> trajectory. It outputs a probabilistic exposure zone, built from many particles run
> under stochastic diffusion, with an explicit confidence figure attached. Higher-resolution
> local current measurements are a Phase 2 item, not a hackathon MVP requirement.

## Evidence, not assertion

This was confirmed empirically while building the ingestion pipeline, not just asserted
from the concept doc:

- Querying HYCOM's `GLBy0.08` grid at the provisional outlet (34.96 N, 29.52 E — Wadi
  Yutum system) returns `nan` — that cell is masked as land/unresolved in the global grid.
- The nearest cell the model resolves as open water is roughly 6 km further into the gulf
  mouth (34.90, 29.40), where it reports a real value (~2–3 cm/s, weak southwestward flow
  on 2026-08-02).
- Only a narrow east–west strip of the AOI (lat ≈ 29.28–29.48) resolves as water at all in
  this grid — see `docs/data_dictionary.md` for the full query.
- **Confirmed with a second independent model (2026-08-03):** Copernicus Marine
  (`GLOBAL_ANALYSISFORECAST_PHY_001_024`) masks the *exact same* outlet cell as
  unresolved/land — this is not a HYCOM-specific quirk, two independently-run global
  ocean models agree the provisional outlet sits outside what either resolves as water.
  At the gulf-mouth point (34.90, 29.40) where both resolve **today**, direction
  agreement was good — under 5° disagreement each time this was checked (currents
  evolve hour to hour, so the exact figure drifts; re-run
  `python -m src.ingestion.ocean_currents` for the current number, in
  `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`'s top row). See
  `compare_hycom_vs_copernicus()` in `backend/src/ingestion/ocean_currents.py`, figure:
  [`docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`](qa_screenshots/currents_01_hycom_vs_copernicus.png).
- **At the actual historical event (2026-08-03, using the correct archival products —
  HYCOM `GLBu0.08/expt_91.2` and Copernicus Marine's GLORYS12V1 reanalysis, not the
  rolling "latest"/"anfc" products used for live forcing, which have no 2016 data at
  all):** the two models' resolved footprints in the narrow gulf **barely overlap at
  all** — a systematic scan of the entire MARINE_AOI at 0.01° resolution found zero
  points both models resolve simultaneously; the nearest shared point is (34.85, 29.30),
  6 km from the outlet. There, at the mooring's peak-response time (2016-10-28 06:50
  UTC), the two models disagree by **65.8°** on current direction (HYCOM 330.8° vs
  Copernicus Marine 36.6°) — far worse than the ~2° agreement seen for today's
  conditions. Both report weak flow (1.4–2.6 cm/s), and direction is intrinsically
  noisy at low speed, which is itself part of the honest picture: **the two best free
  global ocean models cannot agree on which way the water was moving during the actual
  event this project backtests against.** This is a stronger, more specific version of
  the resolution-limitation claim than "the gulf is narrow" — it is measured disagreement
  on the exact date that matters, not a generic caveat.

**For Abd — the one function you need.** `get_historical_interpolator()` in
`backend/src/ingestion/ocean_currents.py` returns a ready `current_fn` for the demo
event window, satisfying `particle_engine.py`'s `current_fn(lon, lat, time, depth) ->
(u, v)` contract directly. It only opens the already-cached
`hycom_aoi_AQ-2016-10-28.nc` / `copernicus_marine_aoi_AQ-2016-10-28.nc` files — no
network call, verified with sockets blocked. Pass it straight into
`particle_engine.simulate(current_fn=get_historical_interpolator(), ...)` in place
of `ConstantCurrentField`.

## What this does and doesn't invalidate

**Does not invalidate:** the forecasting and event-detection pipeline (GFS/GEFS/ECMWF),
which operates on atmospheric grids at a different, generally adequate resolution for
catchment-scale rainfall.

**Correction (2026-08-02):** an earlier version of this section said IoU/centroid
comparisons against "Abd's real satellite mask" were still meaningful for historical
backtesting. That is no longer accurate and must not be repeated. The Sentinel-2/Landsat
extraction for `AQ-2016-10-28` is a documented coastline artifact, not a validated plume —
two independent sensors show no visible plume, and the in-situ mooring record shows the
signal had already returned to background 2.5–3.5 days before either satellite pass (full
reasoning: `docs/event_audit.md`, `docs/pitch_limitations.md`). Spatial metrics (IoU, Dice,
centroid distance) are not computed for this event at all —
`backend/src/models/backtest_metrics.py`'s `assert_spatial_metrics_allowed` refuses to.
**The historical backtest for `AQ-2016-10-28` validates against the Kalman et al. (2025)
mooring time series instead** — arrival-time, duration and peak-timing error, per
`docs/mooring_coordinate_derivation.md` and `data/processed/marine/mooring_target_AQ-2016-10-28.json`.
Does not invalidate the backtesting method itself — only which target it compares against.

**Does invalidate:** any claim that the plume position, arrival time, or shape is exact.
Never present a single trajectory line on the dashboard. Always show:

1. A probability field from many particles, not one path.
2. The resolution number next to the current layer in the UI.
3. The HYCOM-vs-Copernicus-Marine agreement (or disagreement) as an uncertainty signal.
   For today's conditions: under 5° agreement at the gulf mouth (drifts hour to
   hour with live currents). Both models mask the outlet identically regardless
   of when checked. **For the actual demo event (2016-10-28): 65.8° disagreement** — put
   this number on the calibration/scenario slide specifically, not just the generic
   "today" figure, since it's the uncertainty that actually applies to the backtest.
   See `docs/data_dictionary.md` §8 Phase 2 update, 2026-08-03.

## Wind forcing — permanently absent, not a fetch-it-later gap

**Confirmed 2026-08-07.** The particle engine's `wind_fn(lon, lat, time) -> (u10, v10)`
contract (`particle_engine.py`) is currently satisfied by `ConstantWindField(0, 0)` for
the demo event, and this is not a caching gap like the currents files were — **no
historical marine wind source exists anywhere in this repo's ingestion layer:**

- GFS, GEFS and ECMWF (`ecmwf.py`) here are forecast-only products with no 2016 archive
  — the same reason `get_historical_interpolator()` had to reach for HYCOM/Copernicus
  Marine's *reanalysis* products instead of their rolling "latest" ones for currents.
- ERA5-Land does ingest `u10`/`v10` (`era5_land.py`), but **ERA5-Land is land-only —
  sea cells are permanently `NaN`** (see the main project rules). Even a fully cached
  ERA5-Land pull for October 2016 would not cover the marine wind field the particle
  engine needs; this is not a "re-fetch it" gap, it is a wrong-product gap. Plain ERA5
  (non-Land, which does cover sea) is not ingested anywhere in this project.
- No raw ERA5-Land cache exists on this machine at all
  (`data/raw/era5_land/events/`, expected by `scripts/sweep_era5_land_events.py`, is
  absent) — moot given the point above, but checked to be thorough.

**This is now a permanent, named limitation, not a silent zero.** State it alongside
the currents-resolution caveat: wind stress on surface transport is currently
unmodelled for the historical backtest; the `ConstantWindField(0, 0)` is a documented
placeholder, not a claim that October 2016 was windless.

## Judge-ready answer

> "The Gulf is narrower than three grid cells of the best free global ocean model, so we
> don't claim meter-level accuracy — we output probabilistic exposure zones and we tell
> the user our confidence. We verified this isn't theoretical: our own release point sits
> on a masked cell in the global grid, in both models we tried. For the actual October
> 2016 event we backtest against, HYCOM and Copernicus Marine's historical archives
> disagree by 66 degrees on current direction — which is exactly why the plume transport
> step runs an ensemble of particles under stochastic diffusion and reports a probability
> field, not a single confident line. Higher-resolution local current measurements are
> Phase 2, integrated with Marine Science Station data."

This matches the concept doc's own guidance (§23.4): never claim exact prediction; the
correct feasibility claim is end-to-end technical feasibility with explicit, honest
uncertainty.
