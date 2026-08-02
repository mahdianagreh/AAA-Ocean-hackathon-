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
3. The HYCOM-vs-Copernicus-Marine agreement (or disagreement) as an uncertainty signal,
   once Copernicus Marine credentials are available (see `docs/data_dictionary.md` —
   pending as of 2026-08-02).

## Judge-ready answer

> "The Gulf is narrower than three grid cells of the best free global ocean model, so we
> don't claim meter-level accuracy — we output probabilistic exposure zones and we tell
> the user our confidence. We verified this isn't theoretical: our own release point sits
> on a masked cell in the global grid. Higher-resolution local current measurements are
> Phase 2, integrated with Marine Science Station data."

This matches the concept doc's own guidance (§23.4): never claim exact prediction; the
correct feasibility claim is end-to-end technical feasibility with explicit, honest
uncertainty.
