"""Build the full-population training set: every day, not only storm days.

The problem this solves
-----------------------
The delivered matrix is 390 rows drawn from the top 100 rainfall days in 27
years, so 99% of rows had runoff. "Will there be runoff" was answered before
the model saw it, and such a model says yes to a drizzle.

This assembles all 2,362 days present in the ERA5 months on disk - 11,810
catchment-days, 42.7% with exactly zero runoff. Same bytes, no download.

Three things it will not do
---------------------------
1. **Soil moisture for event days only.** If an antecedent column is populated
   on storm days and NaN elsewhere, its mere presence identifies the positive
   class - a leak wearing a different hat. So swvl1 is extracted for every day
   in the same month files, or not used at all.

2. **Discard negatives.** The file keeps all 11,810 rows. Class balancing is a
   per-fold training decision made by the harness, because the test fold must
   stay at natural prevalence: a model that looks 80% precise at a resampled
   20% base rate is much worse at the true 7.9%, and resampling the test set
   hides exactly that.

3. **Use `rank`, or anything static, or anything ERA5-runoff-derived.** The
   feature list is the event-varying columns only.

The threshold
-------------
`sro > 0.002 mm/day`. Anchored, not chosen for balance: the one documented
sediment-delivering flood (Oct 2016, ~24,400 t) peaks at 0.00373 mm, the
94.5th percentile of all catchment-days. A threshold that only barely admits
the sole piece of ground truth would be a bad threshold, so it sits below it.

Output
    data/processed/features/training_set_full.parquet
"""

from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

ERA5_DIR = ROOT / "raw/era5_land/events"
RUNOFF = ROOT / "data/processed/features/daily_runoff_all_days.parquet"
RAINFALL = ROOT / "data/processed/features/catchment_rainfall_daily.parquet"
TERRAIN = ROOT / "data/processed/features/catchment_terrain.parquet"
OUT = ROOT / "data/processed/features/training_set_full.parquet"

MONTH_FILE = re.compile(r"era5_land_(\d{8})T0000_(\d{8})T2300\.nc$")

# See the module docstring. Anchored on the Oct 2016 event at 0.00373 mm.
RUNOFF_THRESHOLD_MM = 0.002
ANCHOR_EVENT_SRO_MM = 0.00373


def catchment_masks(ds):
    """Reused from 13; ERA5 is ~81 km2 per cell against 36-65 km2 catchments."""
    from shapely.geometry import Point

    catch = gpd.read_file(
        ROOT / "data/processed/vectors/catchments.gpkg", layer="catchments"
    ).to_crs(4326)
    lat_name = "lat" if "lat" in ds.coords or "lat" in ds else "latitude"
    lon_name = "lon" if "lon" in ds.coords or "lon" in ds else "longitude"
    LON, LAT = np.meshgrid(np.asarray(ds[lon_name].values, dtype=float),
                           np.asarray(ds[lat_name].values, dtype=float))
    out = {}
    for _, row in catch.iterrows():
        geom = row.geometry
        minx, miny, maxx, maxy = geom.bounds
        near = ((LON >= minx - .15) & (LON <= maxx + .15) &
                (LAT >= miny - .15) & (LAT <= maxy + .15))
        mask = np.zeros_like(LON, dtype=bool)
        for j, i in zip(*np.where(near)):
            if geom.contains(Point(LON[j, i], LAT[j, i])):
                mask[j, i] = True
        if not mask.any():
            c = geom.centroid
            mask[np.unravel_index(np.argmin(np.hypot(LON - c.x, LAT - c.y)),
                                  LON.shape)] = True
        out[row.catchment_id] = mask
    return out


def daily_soil_moisture() -> pd.DataFrame:
    """Daily mean swvl1 per catchment, for EVERY day in the months on disk.

    swvl1 is instantaneous and must never be deaccumulated, so this is a plain
    daily mean of hourly values.
    """
    from ingestion.era5_land import read_era5_land

    files = sorted(p for p in ERA5_DIR.rglob("*.nc") if MONTH_FILE.search(p.name))
    ds0 = read_era5_land(files[0])
    masks = catchment_masks(ds0)
    ds0.close()

    rows = []
    for i, f in enumerate(files, 1):
        try:
            ds = read_era5_land(f)
        except Exception as exc:
            print(f"  SKIP {f.name}: {type(exc).__name__}")
            continue
        if "swvl1" not in ds:
            ds.close()
            continue
        t = pd.to_datetime(ds["time"].values)
        arr = ds["swvl1"].values
        for cid, mask in masks.items():
            s = pd.Series(arr[:, mask].mean(axis=1), index=t)
            daily = s.resample("1D").mean()
            rows.append(pd.DataFrame({
                "date": daily.index, "catchment_id": cid,
                "soil_moisture": daily.values,
            }))
        ds.close()
        if i % 25 == 0 or i == len(files):
            print(f"  swvl1 [{i}/{len(files)}]")
    df = pd.concat(rows, ignore_index=True)
    df["date"] = pd.to_datetime(df.date).dt.tz_localize(None).dt.normalize()
    return df.drop_duplicates(["date", "catchment_id"])


def main():
    print("1/4  soil moisture for every day ...")
    sm = daily_soil_moisture()
    print(f"     {len(sm):,} catchment-days of swvl1")

    print("\n2/4  joining runoff, rainfall, terrain ...")
    y = pd.read_parquet(RUNOFF)
    r = pd.read_parquet(RAINFALL)
    r["date"] = pd.to_datetime(r.timestamp_utc, utc=True).dt.tz_localize(None).dt.normalize()
    # Daily total only. rain_1h/3h/6h/24h exist in the daily record for the 100
    # catalogued storms alone - the half-hourly IMERG sweep covered event
    # windows, not 27 years - so over the full population they are NaN on every
    # row. Carrying them would put four dead columns in front of the model.
    #
    # This is a real loss, not a tidy-up: rain_3h_mm is the strongest physical
    # predictor here, because intensity drives runoff in a hyper-arid catchment
    # rather than daily total. Karam's own ranking shows it - Oct 2016 is 14th
    # by daily total and 8th by peak 3-hour intensity. Recorded in the model
    # card as a stated limitation; adding it means sweeping half-hourly IMERG
    # across the full record.
    rain_cols = ["precipitation_mm_day"]

    df = y.merge(r[["date", "catchment_id"] + rain_cols],
                 on=["date", "catchment_id"], how="left")
    df = df.merge(sm, on=["date", "catchment_id"], how="left")
    print(f"     {len(df):,} rows · rainfall missing {df.precipitation_mm_day.isna().sum()}"
          f" · soil moisture missing {df.soil_moisture.isna().sum()}")

    print("\n3/4  antecedent features from the daily record ...")
    # Rolling priors come from IMERG, so they exist for every day rather than
    # only for storm days - which is the point.
    df = df.sort_values(["catchment_id", "date"]).reset_index(drop=True)
    g = df.groupby("catchment_id", sort=False)
    for w in (1, 3, 7):
        # shift(1) so the window ends the day BEFORE - a same-day sum would
        # include the event's own rain and leak the target.
        df[f"precip_prior_{w}d_mm"] = (
            g.precipitation_mm_day.shift(1).rolling(w, min_periods=1).sum()
             .reset_index(level=0, drop=True)
        )
    df["soil_moisture_lag1d"] = g.soil_moisture.shift(1).reset_index(level=0, drop=True)
    df["soil_moisture_lag3d"] = g.soil_moisture.shift(3).reset_index(level=0, drop=True)

    # Gaps between month-files are real: a shift() across a 4-year gap is not a
    # lag, it is a different decade. Blank those rather than carry them.
    day_gap = g.date.diff().dt.days.reset_index(level=0, drop=True)
    broken = day_gap.isna() | (day_gap > 1)
    for c in ("precip_prior_1d_mm", "precip_prior_3d_mm", "precip_prior_7d_mm",
              "soil_moisture_lag1d", "soil_moisture_lag3d"):
        df.loc[broken, c] = np.nan
    print(f"     {int(broken.sum()):,} rows sit at a month-file boundary; "
          "their lags are NaN, never zero")

    print("\n4/4  target and negative strata ...")
    df["target"] = (df.sro_mm_day > RUNOFF_THRESHOLD_MM).astype(int)
    # Hard negatives are where the boundary is: measurable rain, little runoff.
    df["negative_stratum"] = np.where(
        df.target == 1, "positive",
        np.where(df.precipitation_mm_day >= 0.5, "hard", "easy"))

    terr = pd.read_parquet(TERRAIN)
    df = df.merge(terr[["catchment_id", "area_km2", "slope_mean_deg",
                        "drainage_density_km_km2", "elongation_ratio"]],
                  on="catchment_id", how="left")

    df["runoff_threshold_mm"] = RUNOFF_THRESHOLD_MM
    df["anchor_event_sro_mm"] = ANCHOR_EVENT_SRO_MM
    df = df.sort_values(["date", "catchment_id"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"{len(df):,} rows · {df.date.nunique():,} days · "
          f"{df.date.min().date()} -> {df.date.max().date()}")
    print(f"\ntarget (sro > {RUNOFF_THRESHOLD_MM} mm): "
          f"{int(df.target.sum()):,} positive ({df.target.mean():.1%})")
    print(df.negative_stratum.value_counts().to_string())
    print("\npositives per catchment:")
    print(df.groupby("catchment_id").target.agg(["sum", "mean"]).to_string())
    yr = df.date.dt.year
    print(f"\ntemporal split  <=2014: {(yr <= 2014).sum():,} rows "
          f"({df.loc[yr <= 2014, 'target'].mean():.1%} pos)   "
          f">=2015: {(yr > 2014).sum():,} rows "
          f"({df.loc[yr > 2014, 'target'].mean():.1%} pos)")


if __name__ == "__main__":
    main()
