"""Sub-daily rainfall intensity from the ERA5 month files already on disk.

Why this exists now
-------------------
The sediment formula failed its falsification test: October 2016 - the one
documented 24,400 t event - ranked 193 of 2,362 days. Its rainfall was p99.5
but its ERA5 runoff was only p91.9, and two other days produced 40-57x more
modelled runoff with no documented sediment disaster.

The formula had `sediment ∝ Q`, linear in daily runoff VOLUME. The event that
actually moved the sediment was not high-volume, it was INTENSE - 82% of its
rain in 18 hours, 8th of 83 by peak 3-hour intensity against 14th of 100 by
daily total. Sediment entrainment depends on shear stress, not on how much
water eventually passes.

So intensity is not a nice-to-have. It is the variable that distinguishes the
one event we can check from the days that look bigger and did nothing.

`tp` is hourly in every ERA5 month file, so this needs no download. It trips
the same float32 deaccumulation floor as `sro` and takes the same 1e-7
tolerance - see scripts/13 for the measurement behind that number.

Honest caveat: ERA5 rainfall is reanalysis, smoother than IMERG's satellite
retrieval, and reanalyses are known to damp convective extremes. This is a
WEAKER version of what Karam's half-hourly IMERG sweep will give (83 of 675
events complete as of 4 Aug). Same column names, so swapping to his data later
is a source change, not a rewrite.

Output: data/processed/features/daily_intensity.parquet
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
CATCHMENTS = ROOT / "data/processed/vectors/catchments.gpkg"
OUT = ROOT / "data/processed/features/daily_intensity.parquet"

MONTH_FILE = re.compile(r"era5_land_(\d{8})T0000_(\d{8})T2300\.nc$")


def catchment_masks(ds):
    from shapely.geometry import Point

    catch = gpd.read_file(CATCHMENTS, layer="catchments").to_crs(4326)
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


def intensity_from_month(path: Path, masks) -> pd.DataFrame:
    from ingestion.era5_land import deaccumulate_era5_land, read_era5_land

    ds = read_era5_land(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Same 1e-7 floor as sro: at float32 a near-zero cumulative flickers
        # between 0 and 2**-25, which the 1e-10 default reads as a decrease.
        ds = deaccumulate_era5_land(ds, accumulated_variables=("tp",),
                                    negative_tolerance_m=1e-7)
    var = "total_precipitation_hourly_mm"
    if var not in ds:
        raise KeyError(f"{var} missing; found {sorted(ds.data_vars)}")

    arr = ds[var].values
    t = pd.to_datetime(ds["time"].values)
    rows = []
    for cid, mask in masks.items():
        # nanmean, not mean: ERA5-Land sea cells are permanently NaN and a
        # plain mean returns NaN for the whole catchment.
        s = pd.Series(np.nanmean(arr[:, mask], axis=1), index=t)
        # Increments are labelled by interval END, so shift back an hour to put
        # 00:00 on the day it belongs to - same convention as scripts/13.
        s = s.shift(-1, freq="-1h")
        r1 = s.resample("1D").max()
        r3 = s.rolling(3, min_periods=1).sum().resample("1D").max()
        r6 = s.rolling(6, min_periods=1).sum().resample("1D").max()
        tot = s.resample("1D").sum(min_count=1)
        wet_hours = (s > 0.01).resample("1D").sum()
        # Hour of the daily peak. Afternoon peaks indicate convective heating,
        # nocturnal ones a frontal system - different runoff behaviour.
        peak_hour = s.resample("1D").apply(
            lambda x: float(x.idxmax().hour) if len(x) and x.notna().any()
            else np.nan)
        df = pd.DataFrame({
            "era5_rain_mm_day": tot, "peak_1h_mm": r1,
            "peak_3h_mm": r3, "peak_6h_mm": r6,
            "wet_hours": wet_hours, "peak_hour_utc": peak_hour,
        })
        df.index.name = "date"
        df = df.reset_index()
        df["catchment_id"] = cid
        rows.append(df)
    ds.close()
    return pd.concat(rows, ignore_index=True)


def main():
    files = sorted(p for p in ERA5_DIR.rglob("*.nc") if MONTH_FILE.search(p.name))
    print(f"{len(files)} ERA5 month-files")

    from ingestion.era5_land import read_era5_land
    ds0 = read_era5_land(files[0])
    masks = catchment_masks(ds0)
    ds0.close()

    out = []
    for i, f in enumerate(files, 1):
        try:
            out.append(intensity_from_month(f, masks))
        except Exception as exc:
            print(f"  SKIP {f.name}: {type(exc).__name__}: {exc}")
            continue
        if i % 25 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}]")

    df = pd.concat(out, ignore_index=True)
    df["date"] = pd.to_datetime(df.date).dt.tz_localize(None).dt.normalize()
    df = df.drop_duplicates(["date", "catchment_id"])

    # Concentration: what share of the day's rain fell in its wettest 3 hours.
    # This is the discriminating quantity - two days with the same total and
    # ratios of 0.4 and 0.9 are a drizzle and a cloudburst.
    df["rain_3h_over_daily"] = (
        df.peak_3h_mm / df.era5_rain_mm_day.where(df.era5_rain_mm_day > 0.01))
    df = df.sort_values(["date", "catchment_id"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"{len(df):,} rows · {df.date.nunique():,} days")

    wet = df[df.era5_rain_mm_day > 1.0]
    print(f"\non days with >1 mm ({len(wet):,} rows):")
    for c in ("peak_1h_mm", "peak_3h_mm", "peak_6h_mm", "rain_3h_over_daily",
              "wet_hours"):
        print(f"  {c:20} median {wet[c].median():7.3f}   max {wet[c].max():8.3f}")

    print("\n=== does intensity separate Oct 2016 from the high-volume days? ===")
    c1 = df[df.catchment_id == "AQ-C01"]
    check = c1[c1.date.isin(pd.to_datetime(
        ["2016-10-27", "2016-10-28", "2010-01-18", "2014-03-09"]))]
    print(check[["date", "era5_rain_mm_day", "peak_1h_mm", "peak_3h_mm",
                 "rain_3h_over_daily", "wet_hours"]].to_string(index=False))


if __name__ == "__main__":
    main()
