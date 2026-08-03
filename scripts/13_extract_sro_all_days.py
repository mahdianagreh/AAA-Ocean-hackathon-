"""Extract daily surface runoff for EVERY day in the ERA5 months already on disk.

Why this exists
---------------
The label pipeline was pointed at event days only. But ERA5-Land ships whole
months, and 77 of them are on disk - 2,331 calendar days, of which just 79 are
labelled. The other 2,252 were downloaded, opened, and walked past.

Those days are the negative class the target lacks. The training set is
currently 390 rows at 99% positive because the catalogue is the top 100
rainfall days in 27 years: every row is a storm by construction, so "will
there be runoff" is answered before the model sees it. A model trained on that
says "runoff" to a drizzle.

No download. The bytes are already paid for.

The trap this obeys
-------------------
ERA5-Land accumulates `sro` from 00 UTC to the forecast step, so raw values
must never be summed across timestamps - adding 01:00 + 02:00 counts the first
hour twice. The 00:00 value is the PREVIOUS day's 24-hour total.
`deaccumulate_era5_land()` handles this; see
docs/era5_land_accumulation_semantics.md. This script does not reimplement it.

Output
    data/processed/features/daily_runoff_all_days.parquet
      one row per (date x catchment), with sro_mm_day and ssro_mm_day
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
OUT = ROOT / "data/processed/features/daily_runoff_all_days.parquet"

MONTH_FILE = re.compile(r"era5_land_(\d{8})T0000_(\d{8})T2300\.nc$")


def catchment_masks(ds):
    """Boolean mask per catchment on the ERA5 grid.

    ERA5-Land is ~9 km, so a 36 km2 catchment covers well under one cell. Cell
    centres inside the polygon are used where any exist; otherwise the single
    nearest cell, flagged so the caller knows the value is a point sample and
    not an area mean. Silently returning NaN would drop four of five
    catchments; silently averaging a 9 km cell over a 36 km2 basin without
    saying so would be worse.
    """
    from shapely.geometry import Point

    catch = gpd.read_file(CATCHMENTS, layer="catchments").to_crs(4326)
    # read_era5_land normalises the CDS names, so the coords arrive as lat/lon
    # rather than latitude/longitude. Accept either.
    lat_name = "lat" if "lat" in ds.coords or "lat" in ds else "latitude"
    lon_name = "lon" if "lon" in ds.coords or "lon" in ds else "longitude"
    lats = np.asarray(ds[lat_name].values, dtype=float)
    lons = np.asarray(ds[lon_name].values, dtype=float)
    LON, LAT = np.meshgrid(lons, lats)

    out = {}
    for _, row in catch.iterrows():
        geom = row.geometry
        minx, miny, maxx, maxy = geom.bounds
        near = ((LON >= minx - 0.15) & (LON <= maxx + 0.15) &
                (LAT >= miny - 0.15) & (LAT <= maxy + 0.15))
        mask = np.zeros_like(LON, dtype=bool)
        for j, i in zip(*np.where(near)):
            if geom.contains(Point(LON[j, i], LAT[j, i])):
                mask[j, i] = True
        exact = bool(mask.any())
        if not exact:
            c = geom.centroid
            d = np.hypot(LON - c.x, LAT - c.y)
            mask[np.unravel_index(np.argmin(d), d.shape)] = True
        out[row.catchment_id] = (mask, exact, int(mask.sum()))
    return out


def daily_from_month(path: Path, masks) -> pd.DataFrame:
    from ingestion.era5_land import deaccumulate_era5_land, read_era5_land

    ds = read_era5_land(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # `tp` is excluded because rainfall comes from IMERG; no need to touch it.
        #
        # The tolerance is raised from the 1e-10 default, and the reason is
        # measured rather than assumed. On a dry month the worst "decrease" is
        # a cumulative value going 2.98e-8 -> 0.0, and 2.98e-8 m is exactly
        # 2**-25: one float32 tick. ERA5 stores near-zero runoff as either zero
        # or the smallest representable value and flickers between them, so the
        # decrease is quantisation, not a broken accumulation.
        #
        # Measured on January 2020: 1,244 of 103,277 increments fall below
        # -1e-10; NONE fall below -1e-7. So 1e-7 m clears every violation while
        # staying 58x below the median runoff signal of 5.84e-6 m. It cannot
        # mask a real decrease of any hydrological size.
        #
        # NOTE FOR KARAM: the 1e-10 default is unreachable for this field. It
        # never fired for you because event months carry real runoff, orders of
        # magnitude above the quantum. It fires on every dry month - which is
        # exactly the data the negative class needs.
        ds = deaccumulate_era5_land(
            ds,
            accumulated_variables=("sro", "ssro"),
            negative_tolerance_m=1e-7,
        )

    # Hourly increments are labelled by interval END time, so a UTC day's total
    # is the sum of increments at 01:00..23:00 plus the NEXT day's 00:00.
    # Resampling on the shifted axis expresses that without special-casing.
    rows = []
    for cid, (mask, exact, ncells) in masks.items():
        rec = {}
        # deaccumulate_era5_land emits long names for the mm variants, not
        # <short>_hourly_mm. Asserted below rather than skipped: an earlier
        # version guessed sro_hourly_mm, matched nothing, and produced an empty
        # frame for all 77 months without a single error.
        for var, out_name in (("surface_runoff_hourly_mm", "sro_mm_day"),
                              ("subsurface_runoff_hourly_mm", "ssro_mm_day")):
            if var not in ds:
                raise KeyError(
                    f"{var} missing after deaccumulation; found "
                    f"{sorted(ds.data_vars)}"
                )
            arr = ds[var].values                    # (time, lat, lon)
            series = arr[:, mask].mean(axis=1)      # mean over the catchment
            s = pd.Series(series, index=pd.to_datetime(ds["time"].values))
            # shift back one hour so 00:00 lands on the day it belongs to
            daily = s.shift(-1, freq="-1h").resample("1D").sum(min_count=1)
            rec[out_name] = daily
        if not rec:
            continue
        df = pd.DataFrame(rec)
        df.index.name = "date"
        df = df.reset_index()
        df["catchment_id"] = cid
        df["era5_cells"] = ncells
        df["era5_cell_inside_polygon"] = exact
        rows.append(df)
    ds.close()
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main():
    files = sorted(p for p in ERA5_DIR.rglob("*.nc") if MONTH_FILE.search(p.name))
    if not files:
        raise SystemExit(f"no month files under {ERA5_DIR}")
    print(f"{len(files)} ERA5 month-files")

    from ingestion.era5_land import read_era5_land
    ds0 = read_era5_land(files[0])
    masks = catchment_masks(ds0)
    ds0.close()
    for cid, (_, exact, n) in masks.items():
        print(f"  {cid}: {n} ERA5 cell(s)"
              f"{'' if exact else '  <- POINT SAMPLE, no cell centre inside'}")

    out = []
    for i, f in enumerate(files, 1):
        try:
            out.append(daily_from_month(f, masks))
        except Exception as exc:
            # A month that fails is reported and skipped, never zero-filled.
            print(f"  [{i}/{len(files)}] SKIP {f.name}: {type(exc).__name__}: {exc}")
            continue
        if i % 20 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] {f.name}")

    df = pd.concat(out, ignore_index=True)
    df["date"] = pd.to_datetime(df.date).dt.tz_localize(None).dt.normalize()
    df = df.dropna(subset=["sro_mm_day"]).drop_duplicates(["date", "catchment_id"])
    df = df.sort_values(["date", "catchment_id"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"{len(df):,} rows · {df.date.nunique():,} days · "
          f"{df.catchment_id.nunique()} catchments")
    print(f"span {df.date.min().date()} -> {df.date.max().date()}")

    s = df.sro_mm_day
    print(f"\nsro_mm_day: min {s.min():.6f}  p50 {s.median():.6f}  "
          f"p99 {s.quantile(.99):.4f}  max {s.max():.4f}")
    print(f"  exactly zero : {(s == 0).sum():,}  ({(s == 0).mean():.1%})")
    for t in (0.0, 0.001, 0.005, 0.01, 0.05):
        print(f"  > {t:<6}      : {(s > t).sum():>6,}  ({(s > t).mean():>5.1%})")


if __name__ == "__main__":
    main()
