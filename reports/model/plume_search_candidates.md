# Plume search list for Abd — 31 targeted windows

**Date:** 4 August 2026 · `scripts/25_satellite_plume_candidates.py` ·
output `data/processed/events/plume_search_candidates.csv`

## Why, after a NO-GO

Satellite validation of October 2016 is a measured NO-GO — the plume dispersed
~31 h after arrival and the only usable passes are +104 h and +128 h. **That
verdict is correct and it stands for that event.**

It does not generalise. A ~31 h plume against a ~3-day combined
Sentinel-2 + Landsat-8 revisit has roughly a 43% chance of being caught, so one
event failing is the *expected* outcome. Across every storm in the record the odds
invert:

| | storm days | expected detections |
|---|---:|---:|
| Landsat-8 era (2013-04+) | 31 | — |
| Sentinel-2 era (2015-06+) | 26 | — |
| **either sensor** | **31** | **12.8** |

That roughly doubles the gold set in `scripts/24`. And unlike the 13 literature
floods — recorded at the Kinnet Canal in **Eilat** — a plume off an Aqaba outlet is
evidence on the side of the Gulf our catchments actually drain.

## The search window

From the one event we have timed, both values parsed from `docs/event_dates.md`:

```
arrival      = end of the storm day + 3 h
plume window = arrival .. arrival + 31.42 h
```

Widened by **1.5×** — this is one observation, not a distribution, and
travel time scales with storm location within a 4,453 km² catchment.

The anchor is rain **end**, not rain start. An earlier version used
`rain_start_to_sea_hours` (50 h) from the storm's peak-rainfall day and produced
windows beginning 11 h *after* the documented plume had started — every image
would have come back clear, reading as "no plume" when it meant "wrong dates".
`assert_covers_known_event()` now fails the run unless the window contains the
observed 2016-10-28 plume interval.

## Top 15 by IMERG rainfall

|   priority | date       |   max_imerg_mm | wettest_catchment   | window_start_utc   | window_end_utc    |   p_catch_any |
|-----------:|:-----------|---------------:|:--------------------|:-------------------|:------------------|--------------:|
|          1 | 2014-03-09 |           21.5 | AQ-C05              | 2014-03-09 19:08Z  | 2014-03-11 18:16Z |          0.12 |
|          2 | 2022-01-01 |           21.5 | AQ-C04              | 2022-01-01 19:08Z  | 2022-01-03 18:16Z |          0.47 |
|          5 | 2020-03-12 |           14.4 | AQ-C01              | 2020-03-12 19:08Z  | 2020-03-14 18:16Z |          0.47 |
|          6 | 2016-03-26 |           13.6 | AQ-C01              | 2016-03-26 19:08Z  | 2016-03-28 18:16Z |          0.47 |
|          8 | 2018-12-05 |           11.7 | AQ-C02              | 2018-12-05 19:08Z  | 2018-12-07 18:16Z |          0.47 |
|         11 | 2022-01-09 |           10.5 | AQ-C04              | 2022-01-09 19:08Z  | 2022-01-11 18:16Z |          0.47 |
|         12 | 2014-12-09 |           10.4 | AQ-C01              | 2014-12-09 19:08Z  | 2014-12-11 18:16Z |          0.12 |
|         13 | 2016-10-27 |           10.2 | AQ-C03              | 2016-10-27 19:08Z  | 2016-10-29 18:16Z |          0.47 |
|         14 | 2016-12-23 |           10.2 | AQ-C02              | 2016-12-23 19:08Z  | 2016-12-25 18:16Z |          0.47 |
|         16 | 2016-12-24 |            9.6 | AQ-C01              | 2016-12-24 19:08Z  | 2016-12-26 18:16Z |          0.47 |
|         18 | 2018-04-27 |            9.5 | AQ-C02              | 2018-04-27 19:08Z  | 2018-04-29 18:16Z |          0.47 |
|         19 | 2020-01-10 |            8.8 | AQ-C03              | 2020-01-10 19:08Z  | 2020-01-12 18:16Z |          0.47 |
|         21 | 2019-01-27 |            8.6 | AQ-C03              | 2019-01-27 19:08Z  | 2019-01-29 18:16Z |          0.47 |
|         22 | 2019-02-07 |            8.6 | AQ-C05              | 2019-02-07 19:08Z  | 2019-02-09 18:16Z |          0.47 |
|         24 | 2016-10-28 |            8.3 | AQ-C02              | 2016-10-28 19:08Z  | 2016-10-30 18:16Z |          0.47 |

Ranked by **IMERG**, not ERA5, deliberately: `scripts/24` measured that an IMERG
ranker puts the one documented flood at rank **20 of 2,362** while ERA5 puts it at
**252**. Full list in the CSV.

## What this is not

- **Not a download and not a detection.** This is the search list; the imagery and
  the segmentation are yours.
- **Positives only.** A clear image proves nothing — no plume can mean no plume or
  a missed window. So this can raise recall@K in `scripts/24` and can never make
  precision computable.
- **`AQ-O04` discharges into an enclosed harbour basin.** A plume there settles in
  the basin. If the wettest catchment routes to O04, treat any detection
  separately.
- **Esri World Imagery is licensed for verification and internal review only**, not
  redistribution. Sentinel-2 and Landsat are open; keep any published figure on
  those.
