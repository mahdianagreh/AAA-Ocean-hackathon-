"""Fetch the reference datasets the hydrology chain depends on.

Everything else in scripts/ downloads what it needs, but HydroBASINS,
HydroRIVERS and the country boundaries were originally pulled by hand. That
left the pipeline unreproducible from a clean clone, which this fixes.

All three are open, no registration.

  HydroBASINS L12 eu   provisional catchments (02) + the endorheic check
  HydroRIVERS v10 eu   independent stream validation (08)
  Natural Earth 10m    which country an outlet belongs to (06, 09)

REGION NOTE: HydroSHEDS files the Middle East under 'eu' (Europe & Middle
East), NOT 'as'. The Asia file returns zero basins for Aqaba - a 52 MB
download that yields nothing.

Usage
    .venv/bin/python scripts/00_fetch_reference_data.py
    .venv/bin/python scripts/00_fetch_reference_data.py --keep-zip
"""

import argparse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATASETS = [
    {
        "name": "HydroBASINS level 12 (eu)",
        "url": "https://data.hydrosheds.org/file/hydrobasins/standard/hybas_eu_lev12_v1c.zip",
        "dest": ROOT / "data/raw/hydro",
        "check": "hybas_eu_lev12_v1c.shp",
    },
    {
        "name": "HydroRIVERS v10 (eu)",
        "url": "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_eu_shp.zip",
        "dest": ROOT / "data/raw/hydro",
        "check": "HydroRIVERS_v10_eu_shp/HydroRIVERS_v10_eu.shp",
    },
    {
        "name": "Natural Earth 10m admin 0 countries",
        "url": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
        "dest": ROOT / "data/raw/admin",
        "check": "ne_10m_admin_0_countries.shp",
    },
]


def fetch(ds, keep_zip):
    dest = ds["dest"]
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / ds["check"]).exists():
        print(f"  have  {ds['name']}")
        return
    zip_path = dest / Path(ds["url"]).name
    print(f"  get   {ds['name']} ...", flush=True)
    urllib.request.urlretrieve(ds["url"], zip_path)
    size = zip_path.stat().st_size / 1048576
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    if not keep_zip:
        zip_path.unlink()
    print(f"        {size:.1f} MB extracted to {dest.relative_to(ROOT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-zip", action="store_true",
                    help="keep the archives after extracting")
    args = ap.parse_args()

    print("reference datasets:")
    for ds in DATASETS:
        fetch(ds, args.keep_zip)

    print("\nnot fetched here:")
    print("  Copernicus GLO-30   scripts/03_dem_fetch.py")
    print("  NASA SRTM           scripts/09_srtm_crosscheck.py")
    print("  MERIT Hydro         needs University of Tokyo registration or an")
    print("                      authenticated Earth Engine project - not automated")


if __name__ == "__main__":
    main()
