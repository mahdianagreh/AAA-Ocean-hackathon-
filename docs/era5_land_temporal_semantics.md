# ERA5-Land Temporal Semantics — Evidence and Determination

How ReefShield determined the temporal convention of ERA5-Land flux variables,
with each claim labelled by the strength of its evidence.

Implemented by `normalize_era5_land_fluxes()` and `infer_temporal_semantics()`
in `backend/src/ingestion/era5_land.py`.

---

## A. Facts directly present in file metadata

Read from `data/raw/era5_land/deaccumulation_validation/era5_land_accum_20161026.nc`
(cfgrib-converted, `Conventions = CF-1.7`).

| Variable | `GRIB_stepType` | `GRIB_dataType` | `GRIB_stepUnits` | `units` |
|---|---|---|---|---|
| `tp` | **`accum`** | `fc` (forecast) | `1` (hours) | `m` |
| `sro` | **`accum`** | `fc` | `1` | `m` |
| `ssro` | **`accum`** | `fc` | `1` | `m` |
| `swvl1` | **`instant`** | `an` (analysis) | `1` | `m**3 m**-3` |

Also present: `GRIB_centre = 'ecmf'`, and a `history` attribute recording
`GRIB to CDM+CF via cfgrib-0.9.15.1/ecCodes-2.48.0`.

**What this proves, from the file alone:**

1. `tp`, `sro`, `ssro` are **accumulated** fields (`stepType = accum`). They are
   *not* per-hour values as delivered.
2. `swvl1` is an **instantaneous** analysis state (`stepType = instant`). It
   must never be deaccumulated.
3. The step unit is hours.

**What the file metadata does *not* settle:** the accumulation *period* — i.e.
whether the accumulator resets daily, and what the 00 UTC value covers. The
files carry no `stepRange`, `typeOfStatisticalProcessing`, or forecast-reference
time after cfgrib's CF encoding.

## B. Facts stated by official documentation

From the ECMWF/Copernicus ERA5-Land data documentation
(<https://confluence.ecmwf.int/display/CKB/ERA5-Land%3A+data+documentation>),
retrieved during this work:

> "accumulated from the beginning of the forecast to the end of the forecast
> step. For example, runoff at day=D, step=12 will provide runoff accumulated
> from day=D, time=0 to day=D, time=12."

> "All forecasts start at 00UTC (time=00 hours)."

> "For the CDS time, or validity time, of 00 UTC, the accumulations are over
> the 24 hours ending at 00 UTC i.e. the accumulation is during the previous
> day."

**What this adds:** the reset period is **daily at 00 UTC**, and the value
stamped 00 UTC is the **previous** calendar day's 24-hour total. Combined with
section A, the convention is fully determined.

## C. Observed values in the smoke-test files

Observations only — **not used as evidence** for the convention.

- Six-hour multi-variable file (2016-10-27 00:00–05:00): `tp` per-step means
  were `1.463e-4, 0, 0, 0, 0, 0` m; `sro` similar; `ssro` identically zero.
- Two-day validation window: after reset-aware deaccumulation, each day's 24
  increments reproduced the following 00 UTC raw total to within GRIB
  quantisation.
- Negative increments occurred only at exactly `-7.45e-9` (2⁻²⁷) and
  `-1.49e-8` m (2⁻²⁶) — GRIB packing steps, 11 of 1632 values.

**Why observation is not evidence.** A dry window makes an accumulated field
look flat, and a wet first hour makes it look monotonic. Inferring convention
from value behaviour would give different answers for different weather. The
implementation therefore refuses to use it: `mode="auto"` reads metadata only.

## D. Engineering assumptions

1. **Interval-end labelling.** Derived hourly values are labelled by the end of
   the interval they cover, matching the raw stamps. A day is `T01:00` →
   `T+1 T00:00`.
2. **Unresolvable first interval → NaN.** When the leading timestamp is not
   01 UTC and has no predecessor, the increment is unknown. NaN, never zero.
3. **Negative tolerance is caller-supplied.** The default `1e-10 m` suits
   float64 noise; real GRIB-packed data needs ~`1e-7 m`. See
   `docs/era5_land_accumulation_semantics.md`.
4. **`mm = m * 1000`, applied after deaccumulation**, never before.
5. **Sea-mask NaNs are never filled.**

## E. Unresolved ambiguity

1. **Sub-hourly or non-hourly requests are untested.** All evidence here is for
   an hourly axis. `normalize_era5_land_fluxes` requires continuous hourly
   timestamps in cumulative mode and raises otherwise.
2. **ERA5-Land vs ERA5 differences** in accumulation handling are not
   investigated; only ERA5-Land is used.
3. **`expver` / `number` coordinates** appear in the files but their role
   (ERA5T vs final release) has not been examined. If a window ever mixes
   `expver` values, results should be re-checked.
4. **Whether other CDS delivery formats** (GRIB direct, zarr) carry the same
   `stepType` attribute is unknown — `mode="auto"` will simply raise if the
   attribute is absent, which is the intended safe behaviour.

## F. Determination and implementation

| Field | Mode | Basis |
|---|---|---|
| `tp`, `sro`, `ssro` | **cumulative** | A (`stepType=accum`) + B (daily reset at 00 UTC) |
| `swvl1` | **instantaneous** | A (`stepType=instant`) — never deaccumulated |

`normalize_era5_land_fluxes(dataset, mode="auto")` resolves this at runtime:

1. Honour an explicit `temporal_semantics_mode` attribute if a previous
   normalisation wrote one.
2. Otherwise require `GRIB_stepType` on every flux variable. `accum` →
   cumulative. `instant` on a flux → error. Missing or mixed → error.
3. Never inspect values.

Failure raises `ERA5LandTemporalSemanticsError` with instructions to pass an
explicit mode citing documentation — the pipeline does not guess.

Every normalised variable and the dataset carry `temporal_semantics_mode` and
`temporal_semantics_evidence`, so any downstream consumer can see *why* the
field was treated the way it was.
