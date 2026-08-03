"""Scene-metadata audit for Abd's plume-validation gate (tasks/abd.md §1-3).

Anonymous metadata search only — no credentials required. Finds candidate
Sentinel-2 and Landsat scenes around each event window and reports scene-level
cloud cover. This is NOT the final gate: cloud % here is scene-wide, not
computed over the AOI water mask, and no visual QC (plume visibility, sun
glint) is performed. See docs/event_audit.md §4 for what's still blocked.

Sentinel-2 goes through the official Copernicus Data Space OData catalog
rather than the Earth Search AWS mirror: the AWS mirror has zero scenes for
these tiles before 2017-01-01 despite claiming a 2015-06-27 temporal extent.
See docs/event_audit.md §0 for how that gap was caught.

Reproduce:
    source .venv/bin/activate && python scripts/audit_satellite_scenes.py
"""

from datetime import datetime, timedelta

import requests
from pystac_client import Client

from pulga_config import DOWNLOAD_BBOX

CDSE_ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"


def _aoi_polygon_wkt(bbox):
    w, s, e, n = bbox
    return f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"


def search_sentinel2_cdse(bbox, start, end):
    """Anonymous OData search against the official Copernicus catalog.

    start/end are date strings 'YYYY-MM-DD'; queried as a half-open UTC window.
    """
    filt = (
        "Collection/Name eq 'SENTINEL-2' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{_aoi_polygon_wkt(bbox)}') and "
        f"ContentDate/Start gt {start}T00:00:00.000Z and "
        f"ContentDate/Start lt {end}T00:00:00.000Z and "
        "contains(Name,'MSIL2A')"
    )
    params = {
        "$filter": filt,
        "$top": 50,
        "$orderby": "ContentDate/Start asc",
        "$expand": "Attributes",
    }
    r = requests.get(CDSE_ODATA_URL, params=params, timeout=30)
    r.raise_for_status()
    rows = []
    for p in r.json().get("value", []):
        attrs = {a["Name"]: a["Value"] for a in p.get("Attributes", [])}
        rows.append(
            {
                "name": p["Name"],
                "id": p["Id"],
                "start_utc": p["ContentDate"]["Start"],
                "cloud_cover_pct": attrs.get("cloudCover"),
                "tile": attrs.get("tileId"),
            }
        )
    return rows


def search_landsat_earthsearch(bbox, start, end):
    """Anonymous STAC search; Earth Search mirrors the full USGS Landsat C2 L2 archive."""
    client = Client.open(EARTH_SEARCH_URL)
    search = client.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=f"{start}/{end}",
        sortby=[{"field": "properties.datetime", "direction": "asc"}],
    )
    rows = []
    for item in search.items():
        rows.append(
            {
                "id": item.id,
                "datetime": str(item.datetime),
                "cloud_cover_pct": item.properties.get("eo:cloud_cover"),
                "platform": item.properties.get("platform"),
            }
        )
    return rows


def days_from(event_dt, scene_dt):
    return round((scene_dt - event_dt).total_seconds() / 86400, 1)


if __name__ == "__main__":
    # --- Event AQ-2016-10-28 : flood arrival 2016-10-28T00:00:00Z ------------
    event_oct2016 = datetime(2016, 10, 28)
    win_start, win_end = "2016-10-18", "2016-11-07"  # +/- 10 days per abd.md gate
    print(f"=== Sentinel-2, AQ-2016-10-28, window {win_start} to {win_end} ===")
    for row in search_sentinel2_cdse(DOWNLOAD_BBOX, win_start, win_end):
        dt = datetime.fromisoformat(row["start_utc"].replace("Z", "+00:00")).replace(tzinfo=None)
        print(
            f"{row['name']:65s} tile={row['tile']:6s} "
            f"days_from_event={days_from(event_oct2016, dt):+.1f} "
            f"cloud={row['cloud_cover_pct']}"
        )

    # --- Backup event: Feb 2013, exact day unresolved (docs/event_dates.md) --
    print("\n=== Landsat, Feb 2013 (whole month - exact day not yet resolved) ===")
    for row in search_landsat_earthsearch(DOWNLOAD_BBOX, "2013-02-01", "2013-02-28"):
        print(f"{row['id']:35s} {row['datetime']} cloud={row['cloud_cover_pct']} platform={row['platform']}")

    print(
        "\nNo Sentinel-2 search run for Feb 2013: S2A launched 2015-06-27, "
        "over two years after this event - confirmed impossible, not just unlikely."
    )
