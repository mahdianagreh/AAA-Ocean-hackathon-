"""Run the AQ-2016-10-28 plume-extraction pipeline end to end.

Pre-event baseline: clearest available 2016 Sentinel-2 scenes before the flood
(S2A-only cadence in 2016, so this searches Jun-Oct rather than a tight
±10-day window — the ±10-day window is the *post-event gate*, not the
baseline requirement; see docs/event_audit.md Section 1).
Post-event candidate: 2016-11-02, the only scene that clears the numeric gate
(docs/event_audit.md Section 1).

Reproduce:
    cd scripts && ../.venv/bin/python run_plume_extraction.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# NOTE (Pulga, 2 Aug 2026): this file imported ANALYSIS_BBOX, which the AOI v2
# migration removed — the script could not even import. Substituted MARINE_BBOX,
# because contract §1 assigns imagery to MARINE_AOI, and the old ANALYSIS_BBOX
# (34.90, 29.35, 35.05, 29.60) is a near-subset of it (34.80, 29.25, 35.05, 29.60).
# The scene search therefore covers slightly MORE sea than before, never less.
# Flagging rather than silently rewriting: if you wanted the tighter box, say so.
from pulga_config import MARINE_BBOX as ANALYSIS_BBOX  # noqa: E402
from pulga_config import PROCESSED, VECTORS, QA  # noqa: E402

sys.path.append(str(Path(__file__).resolve().parent.parent / "backend" / "src"))
from models import plume_segmentation as ps  # noqa: E402

PLUME_DIR = PROCESSED / "plume"
PLUME_DIR.mkdir(parents=True, exist_ok=True)
VECTORS.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)

BASELINE_WINDOW = "2016-06-01/2016-10-18"
POST_EVENT_WINDOW = "2016-11-02/2016-11-03"
MAX_BASELINE_SCENES = 8
MAX_BASELINE_CLOUD = 5.0  # percent, scene-level; all candidates here are far below this


def write_geotiff(path, array, transform, crs, dtype="float32", nodata=None):
    with rasterio.open(
        path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
        count=1, dtype=dtype, crs=crs, transform=transform, nodata=nodata,
    ) as dst:
        dst.write(array.astype(dtype), 1)


if __name__ == "__main__":
    print("=== Searching baseline (pre-event) scenes ===")
    baseline_items = ps.search_scenes(ANALYSIS_BBOX, BASELINE_WINDOW, max_cloud=MAX_BASELINE_CLOUD)
    baseline_items = baseline_items[:MAX_BASELINE_SCENES]
    for it in baseline_items:
        print(f"  {it.id}  cloud={it.properties.get('eo:cloud_cover'):.2f}%")
    if len(baseline_items) < 3:
        raise SystemExit("Too few clear baseline scenes found — aborting.")

    print("\n=== Loading baseline scene bands ===")
    baseline_bands, transform, crs = [], None, None
    for it in baseline_items:
        bands, transform, crs = ps.load_scene_bands(it, ANALYSIS_BBOX)
        baseline_bands.append(bands)
        print(f"  loaded {it.id}, grid shape {bands['SCL'].shape}")

    print("\n=== Deriving stable water mask (SCL majority vote across baseline scenes) ===")
    water_mask = ps.stable_water_mask(baseline_bands, min_fraction=0.5)
    print(f"  water pixels: {water_mask.sum()} / {water_mask.size} ({100*water_mask.mean():.1f}%)")

    # Erode the water mask by 1 pixel (20 m) to keep mixed coastal pixels out of the anomaly.
    from scipy.ndimage import binary_erosion
    water_mask_eroded = binary_erosion(water_mask, iterations=1)

    print("\n=== Building baseline composite + indices ===")
    composite = ps.baseline_composite(baseline_bands)
    baseline_idx = ps.spectral_indices(composite)
    write_geotiff(PLUME_DIR / "baseline_composite.tif", composite["B04"], transform, crs)
    print(f"  saved {PLUME_DIR / 'baseline_composite.tif'} (red band of composite)")

    print("\n=== Loading post-event scene (2016-11-02) ===")
    post_items = ps.search_scenes(ANALYSIS_BBOX, POST_EVENT_WINDOW)
    post_item = post_items[0]
    print(f"  {post_item.id}  cloud={post_item.properties.get('eo:cloud_cover'):.2f}%")
    post_bands, post_transform, post_crs = ps.load_scene_bands(post_item, ANALYSIS_BBOX)
    post_idx = ps.spectral_indices(post_bands)

    print("\n=== AOI-water cloud % (the actual gate metric, not scene-level metadata) ===")
    unusable = ps.unusable_mask(post_bands)
    water_and_unusable = water_mask & unusable
    aoi_water_cloud_pct = 100 * water_and_unusable.sum() / max(water_mask.sum(), 1)
    print(f"  cloud/shadow fraction over AOI water: {aoi_water_cloud_pct:.2f}%")

    glint = ps.glint_mask(post_bands)
    water_and_glint = water_mask & glint
    print(f"  suspected-glint fraction over AOI water: {100*water_and_glint.sum()/max(water_mask.sum(),1):.2f}%")

    valid_mask = water_mask_eroded & (~unusable) & (~glint)
    print(f"  valid (water, clear, non-glint, eroded) pixels for anomaly: {valid_mask.sum()}")

    print("\n=== Computing anomalies for all 4 candidate indices ===")
    anomalies = ps.anomaly(baseline_idx, post_idx, valid_mask)
    for key, arr in anomalies.items():
        valid = arr[~np.isnan(arr)]
        if valid.size:
            print(f"  {key:20s} mean={np.nanmean(arr):+.5f}  p95={np.nanpercentile(valid,95):+.5f}  p99.5={np.nanpercentile(valid,99.5):+.5f}")

    # --- comparison figure: all 4 indices side by side ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 14))
    for ax, key in zip(axes.flat, ["ndssi", "nsmi", "red_green_ratio", "red_reflectance"]):
        im = ax.imshow(anomalies[key], cmap="RdBu_r", vmin=-np.nanpercentile(np.abs(anomalies[key]), 98),
                        vmax=np.nanpercentile(np.abs(anomalies[key]), 98))
        ax.set_title(f"Anomaly: {key}")
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046)
    plt.suptitle("AQ-2016-10-28 candidate spectral indices — post(11-02) minus baseline composite")
    fig.savefig(QA / "plume_index_comparison_AQ-2016-10-28.png", dpi=130, bbox_inches="tight")
    print(f"\nSaved comparison figure: {QA / 'plume_index_comparison_AQ-2016-10-28.png'}")

    # --- primary index: red-band reflectance anomaly (simplest, most directly
    # physically interpretable: sediment-laden water reflects more red light) ---
    primary = anomalies["red_reflectance"]
    probability = ps.anomaly_to_probability(primary)
    write_geotiff(PLUME_DIR / "observed_plume_probability.tif", probability, transform, crs)
    print(f"Saved probability raster: {PLUME_DIR / 'observed_plume_probability.tif'}")

    geoms, out_crs = ps.probability_to_polygons(probability, transform, crs, threshold=0.7)
    print(f"\n=== Vectorization: {len(geoms)} candidate polygon(s) above threshold 0.7 ===")
    if geoms:
        gdf = gpd.GeoDataFrame({"geometry": geoms, "probability_threshold": 0.7}, crs=out_crs)
        gdf.to_file(VECTORS / "observed_plume.gpkg", driver="GPKG")
        print(f"  total area: {gdf.geometry.area.sum():.0f} m^2")
        print(f"  saved {VECTORS / 'observed_plume.gpkg'}")
    else:
        print("  NO polygons above threshold — no plume signal detected at this scene/date.")
        gdf = gpd.GeoDataFrame({"geometry": [], "probability_threshold": []}, crs=crs)
        gdf.to_file(VECTORS / "observed_plume.gpkg", driver="GPKG")
        print(f"  saved EMPTY {VECTORS / 'observed_plume.gpkg'} (documents the null result, not an error)")
