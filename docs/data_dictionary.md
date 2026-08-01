# ReefShield Data Dictionary

One row per source variable, from provider to processed output. Every entry
reflects what was actually retrieved and verified in this workstream.

Access dates in this document: **2026-08-01** (IMERG Early; ERA5-Land example
windows) and **2026-07-31 / 2026-08-01** (IMERG Final Oct 2016 window).

---

## 1. NASA GPM IMERG V07 — Final Run

| Field | Value |
|---|---|
| Source organization | NASA / JAXA (GPM mission), distributed by NASA GES DISC |
| Dataset name | GPM IMERG Final Precipitation L3 Half Hourly 0.1° |
| Product / version | `GPM_3IMERGHH`, version **07** (files V07B) |
| Collection concept ID | `C2723754847-GES_DISC` |
| Run type | **final** — gauge-adjusted, calibrated |
| Suitable for training | **Yes** |
| Access method | NASA Harmony spatial + variable subsetting (`harmony-py`), auth via `earthaccess` |
| Registration required | Yes — NASA Earthdata account **plus** one-time approval of *NASA GESDISC DATA ARCHIVE* |
| Licence / terms status | Accepted (EULA approved 2026-08-01; blocked downloads until then) |
| Native format | HDF5 (global) |
| Processed format | NetCDF4 subset (~44 KB per granule vs ~7.6 MB global) |
| Temporal resolution | 30 minutes |
| Time availability | 2000-06 → present (Final lags ~3.5 months) |
| Spatial resolution | 0.1° (~11 km) |
| Geographic extent used | 34.80–35.15 °E, 29.25–29.70 °N (5 lat × 4 lon cells) |
| Raw path | `data/raw/imerg/events/<event_id>/` |
| Processed path | `data/processed/events/<event_id>/<event_id>_imerg.nc` |
| Citation | https://gpm.nasa.gov/data/imerg |

| Variable | Internal name | Units | Missing-data semantics | Transformation |
|---|---|---|---|---|
| `Grid/precipitation` | `precipitation` | mm/hr | `_FillValue = -9999.9` → NaN; never zero | transpose `(time, lon, lat)` → `(time, lat, lon)` |
| derived | `precipitation_depth_mm` | mm | NaN propagates | `rate × 0.5 h` |
| derived | `rain_1h_mm`, `rain_3h_mm`, `rain_6h_mm`, `rain_24h_mm` | mm | NaN if any interval missing (`skipna=False`) | trailing rolling sums, `min_periods` = full window |
| `Grid/lat`, `Grid/lon` | `lat`, `lon` | degrees | — | ascending |
| `Grid/time` | `time` | UTC | — | cftime `DatetimeJulian`, epoch 1980-01-06 |
| `Grid/lat_bnds`, `lon_bnds`, `time_bnds` | same | — | — | carried through, used for cell footprints |

**Limitations.** ~11 km cells smooth the localized convective storms that cause
Aqaba flash floods — a documented product limitation, not a pipeline defect.
The delivered array is `(time, lon, lat)`; index-order errors are silent.
Harmony does **not** concatenate — one file per granule.

---

## 2. NASA GPM IMERG V07 — Early Run

| Field | Value |
|---|---|
| Source organization | NASA / JAXA, GES DISC |
| Dataset name | GPM IMERG Early Precipitation L3 Half Hourly 0.1° |
| Product / version | `GPM_3IMERGHHE`, version **07** (files V07C) |
| Collection concept ID | `C2723758340-GES_DISC` (resolved from CMR, Harmony-verified) |
| Run type | **early** — preliminary, uncalibrated |
| Suitable for training | **No** — `preliminary=true`, `calibrated_final_product=false` |
| Observed latency | **6.1 h** measured 2026-08-01 (latest granule 08:00 UTC at 14:06 UTC) |
| Access method | Same Harmony path as Final; separate collection ID |
| Registration required | Same Earthdata account and GES DISC approval |
| Licence / terms status | Accepted |
| Native / processed format | HDF5 → NetCDF4 subset |
| Temporal / spatial resolution | 30 minutes / 0.1° |
| Time availability | ~4–6 h behind real time |
| Raw path | `data/raw/imerg/early_live/` |
| Processed path | `data/processed/live/imerg_early_latest.nc` |
| Citation | https://gpm.nasa.gov/data/imerg |

Variables identical to Final Run. Every output carries `imerg_run_type="early"`,
and Early results are written to `live/` so they can never overwrite Final Run
files.

**Limitations.** Preliminary values are revised in Late and Final runs.
**Granules can be missing**: on 2026-08-01 the 07:00 UTC granule was absent
(83.33 % window completeness). Gaps are reported and the longest contiguous run
is processed; nothing is interpolated.

---

## 3. ERA5-Land Hourly

| Field | Value |
|---|---|
| Source organization | ECMWF / Copernicus Climate Change Service (C3S) |
| Dataset name | ERA5-Land hourly data from 1950 to present |
| Product / version | `reanalysis-era5-land` (ERA5-Land) |
| Run type | reanalysis (not applicable to Final/Early distinction) |
| Access method | Copernicus CDS API (`cdsapi` ≥ 0.7.7), credentials in `~/.cdsapirc` |
| Registration required | Yes — CDS account **plus** one-time ERA5-Land licence acceptance |
| Licence / terms status | Accepted 2026-08-01 (403 "required licences not accepted" until then) |
| Native format | GRIB, converted server-side to NetCDF (cfgrib 0.9.15.1 / ecCodes 2.48.0) |
| Processed format | NetCDF4 |
| Temporal resolution | 1 hour |
| Time availability | 1950 → present (~5-day lag) |
| Spatial resolution | 0.1° (~9 km native) |
| Geographic extent used | CDS area `[29.70, 34.80, 29.25, 35.15]` → 5 lat × 4 lon |
| Raw path | `data/raw/era5_land/events/<event_id>/` |
| Processed path | `data/processed/events/<event_id>/<event_id>_era5_land.nc` |
| Citation | https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land |

| CDS variable | Short name | Internal name | Units | `GRIB_stepType` | Missing-data semantics | Transformation |
|---|---|---|---|---|---|---|
| `volumetric_soil_water_layer_1` | `swvl1` | `swvl1` | m³ m⁻³ | `instant` | permanent sea mask → NaN | negatives in `[-1e-12, 0)` → 0; **never deaccumulated** |
| `total_precipitation` | `tp` | `total_precipitation_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | reset-aware deaccumulation, then × 1000 |
| `surface_runoff` | `sro` | `surface_runoff_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | same |
| `sub_surface_runoff` | `ssro` | `subsurface_runoff_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | same |
| `10m_u_component_of_wind` | `u10` | `u10` | m s⁻¹ | `instant` | NaN preserved | none — negatives are physical |
| `10m_v_component_of_wind` | `v10` | `v10` | m s⁻¹ | `instant` | NaN preserved | none |
| `2m_temperature` | `t2m` | `t2m` | K | `instant` | NaN preserved | none — **not** converted to °C |

**Limitations.**
- **Land-only.** 3 of 20 cells over the Gulf of Aqaba are permanently NaN, and
  the mask is identical across all seven variables.
- **Accumulations reset daily at 00 UTC**, and the 00 UTC value is the previous
  day's 24-hour total. See `docs/era5_land_temporal_semantics.md`.
- **GRIB quantisation** produces negative increments of exactly −7.45e−9 and
  −1.49e−8 m; the module default tolerance of 1e-10 m is too tight for real
  data (use 1e-7 m).
- **CDS expands `year × month × day × time` as a product** — cross-midnight
  partial windows over-request. The pipeline chunks daily to prevent this.
- Latitude is delivered **descending**; normalised to ascending on read.

---

## 4. Derived antecedent features

Produced by `backend/src/processing/antecedent_features.py`; written to
`<event_id>_antecedent_features.parquet`.

| Feature | Units | Definition |
|---|---|---|
| `soil_moisture_t_minus_24h`, `_72h` | m³ m⁻³ | `swvl1` sampled at the exact lag |
| `precipitation_prior_24h_mm`, `_72h_mm`, `_7d_mm` | mm | sum over `(event − N h, event]` |
| `surface_runoff_prior_*`, `subsurface_runoff_prior_*` | mm | same windows |
| `u10_event_time`, `v10_event_time` | m s⁻¹ | value at the event hour |
| `wind_speed_event_time` | m s⁻¹ | `sqrt(u10² + v10²)` |
| `wind_direction_event_time` | degrees | **meteorological**: bearing the wind blows **from**; `(270 − deg(atan2(v, u))) mod 360` |
| `temperature_2m_event_time` | K | value at the event hour |
| `mean_wind_speed_prior_state_window`, `mean_temperature_...` | m s⁻¹, K | mean over the trailing state window |
| `<feature>_valid_fraction` | 1 | share of the window with usable data |
| `valid_data_fraction` | 1 | minimum across all features |
| `quality_flag` | — | `GOOD` / `MISSING_DATA` / `PARTIAL_WINDOW` / `NO_DATA` |

Missing hours are excluded from sums and reduce the valid fraction — never
treated as zero.

---

## 5. Rainfall candidates

`data/processed/events/rainfall_candidates.parquet`. Columns per the Phase 7
contract, including `candidate_generation_scope`, `search_scope_start_utc`,
`search_scope_end_utc` and **`is_exhaustive`**.

> **`is_exhaustive = false`** for everything produced so far. The table covers
> only the configured demonstration windows and is **not** a complete
> historical event catalogue.

---

## 6. CHIRPS — not executed

| Field | Value |
|---|---|
| Source organization | UCSB Climate Hazards Center / USGS |
| Dataset name | CHIRPS (Climate Hazards InfraRed Precipitation with Station data) |
| Status | **Out of scope for this workstream — not retrieved, not evaluated** |
| Reason | IMERG Final + Early already satisfy the rainfall requirement; CHIRPS was never part of the executed plan |
| Registration | None required (open access) |
| Note | Listed only so its absence is explicit rather than an oversight. No CHIRPS data exists anywhere in this repository. |

---

## 7. Cross-product warning

**ERA5-Land and IMERG grids are not index-aligned.** Both are 0.1° and both are
5 × 4 over this box, which makes index pairing look plausible — it is wrong:

```
IMERG lat: 29.25 29.35 29.45 29.55 29.65   (ascending)
ERA5  lat: 29.30 29.40 29.50 29.60 29.70   (after normalisation)
IMERG lon: 34.85 34.95 35.05 35.15
ERA5  lon: 34.80 34.90 35.00 35.10
```

Cell centres are offset by half a cell. Any spatial combination must use
area-weighted overlap or catchment aggregation. No index-based merge exists
anywhere in this codebase.
