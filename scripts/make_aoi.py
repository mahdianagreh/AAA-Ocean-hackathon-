"""Step 2.1 — write the AOI boxes to disk so every clip references a file, not a typed tuple.

Produces:
  data/raw/aoi/aqaba_padded_box.geojson   (download superset, contract §1)
  data/aoi/aqaba_aoi.geojson              (exact analysis box, contract §3 path)
"""

import geopandas as gpd
from shapely.geometry import box

from config import (
    ANALYSIS_BBOX,
    ANALYSIS_BOX_PATH,
    AOI_CRS_PROJECTED,
    AOI_CRS_STORAGE,
    DOWNLOAD_BBOX,
    PADDED_BOX_PATH,
)


def write_box(bbox, path, name, verified):
    minx, miny, maxx, maxy = bbox
    gdf = gpd.GeoDataFrame(
        {"name": [name], "verified": [verified], "geometry": [box(minx, miny, maxx, maxy)]},
        crs=AOI_CRS_STORAGE,
    )
    # Area from the projected CRS only — degrees² is meaningless (contract §1).
    gdf["area_km2"] = gdf.to_crs(AOI_CRS_PROJECTED).geometry.area / 1e6
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")
    print(f"wrote {path.relative_to(path.parents[2])}  bbox={bbox}  area={gdf.area_km2[0]:,.0f} km2")
    return gdf


if __name__ == "__main__":
    write_box(DOWNLOAD_BBOX, PADDED_BOX_PATH, "aqaba_download_padded_box", True)
    write_box(ANALYSIS_BBOX, ANALYSIS_BOX_PATH, "aqaba_analysis_box", False)

    # Guard: the analysis box must sit inside the download box, or downloads
    # clipped to the padded box will not cover the analysis area.
    pad = box(*DOWNLOAD_BBOX)
    ana = box(*ANALYSIS_BBOX)
    assert pad.contains(ana), "ANALYSIS_BBOX escapes DOWNLOAD_BBOX — re-check contract §1"
    print("OK: analysis box is contained by the padded download box")
