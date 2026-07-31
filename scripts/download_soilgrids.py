"""Download ISRIC SoilGrids v2.0 rasters for the padded AOI via WCS.

Writes data/raw/soilgrids/<variable>_<depth>_mean.tif (EPSG:4326, ~250 m).

Why WCS and not the REST API: the REST endpoint is point-based, so aggregating
it to catchment means would mean sampling a point grid and averaging samples.
WCS returns an actual raster, which lets us use the same zonal-statistics path
as WorldCover and weight every 250 m cell that falls in a catchment.
"""

import time

import requests

from config import DOWNLOAD_BBOX, RAW

VARIABLES = ["clay", "sand", "silt", "soc", "bdod", "cfvo"]
DEPTHS = ["0-5cm", "5-15cm"]

BASE = "https://maps.isric.org/mapserv"
OUT = RAW / "soilgrids"


def download(variable: str, depth: str, retries: int = 3) -> bool:
    minx, miny, maxx, maxy = DOWNLOAD_BBOX
    coverage = f"{variable}_{depth}_mean"
    params = {
        "map": f"/map/{variable}.map",
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": coverage,
        "FORMAT": "GEOTIFF_INT16",
        "SUBSET": [f"long({minx},{maxx})", f"lat({miny},{maxy})"],
        "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
        "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
    }
    dst = OUT / f"{coverage}.tif"

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(BASE, params=params, timeout=180)
            r.raise_for_status()
            # ISRIC returns an XML ows:ExceptionReport with HTTP 200 on failure,
            # so status code alone is not proof of a raster. Check the magic bytes.
            if r.content[:4] not in (b"II*\x00", b"MM\x00*"):
                snippet = r.content[:200].decode("utf-8", "replace")
                print(f"  {coverage}: not a TIFF (attempt {attempt}) — {snippet}")
                time.sleep(3 * attempt)
                continue
            dst.write_bytes(r.content)
            print(f"  {coverage}: {len(r.content) / 1024:.0f} KB")
            return True
        except requests.RequestException as e:
            print(f"  {coverage}: {type(e).__name__} (attempt {attempt}) — {e}")
            time.sleep(3 * attempt)
    print(f"  {coverage}: FAILED after {retries} attempts")
    return False


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    ok, bad = [], []
    for variable in VARIABLES:
        for depth in DEPTHS:
            (ok if download(variable, depth) else bad).append(f"{variable}_{depth}")
    print(f"\ndownloaded {len(ok)}/{len(ok) + len(bad)}")
    if bad:
        print("FAILED: " + ", ".join(bad))
