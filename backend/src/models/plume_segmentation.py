"""Sediment plume detection from Sentinel-2 L2A — spectral anomaly approach.

Per tasks/abd.md Section 4 (concept doc Section 10.5): baseline composite ->
water mask -> spectral indices -> anomaly detection -> artifact removal ->
probability raster -> manual QC. Deliberately not a segmentation model — the
Aqaba-specific labeled set is far too small for that to mean anything in a
two-week MVP, and a spectral anomaly is what can actually be checked by eye.

All bands are read at the 20 m grid (SCL's native resolution): the 10 m bands
(B02/B03/B04/B08) are area-averaged down to it on read. This trades resolution
for having every band on one aligned grid without a separate resampling step.

Pixel access: Microsoft Planetary Computer (public, no credentials). Chosen
because the AWS Earth Search mirror has no scenes for this tile before
2017-01-01, and Copernicus Data Space needs a login for actual pixel bytes
(only metadata search is anonymous there). See docs/event_audit.md Section 0.
"""

import numpy as np
import planetary_computer as pc
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.features import shapes as raster_shapes
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely.geometry import shape

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
S2_10M_BANDS = ["B02", "B03", "B04", "B08"]
S2_20M_BANDS = ["B11", "B12", "SCL"]
S2_ALL_BANDS = S2_10M_BANDS + S2_20M_BANDS

SCL_WATER = 6
SCL_CLOUD_SHADOW = 3
SCL_CLOUD_CLASSES = {8, 9, 10}  # medium prob, high prob, thin cirrus
SCL_UNUSABLE = SCL_CLOUD_CLASSES | {SCL_CLOUD_SHADOW, 0, 1}  # + nodata, saturated/defective

REFLECTANCE_SCALE = 1.0 / 10000.0  # Sentinel-2 L2A boa_add_offset-free DN -> reflectance


def search_scenes(bbox_4326, date_range, max_cloud=None):
    """Anonymous STAC search against Planetary Computer; returns signed items."""
    client = Client.open(PC_STAC_URL)
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox_4326,
        datetime=date_range,
        sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    )
    items = [pc.sign(item) for item in search.items()]
    if max_cloud is not None:
        items = [it for it in items if it.properties.get("eo:cloud_cover", 100) <= max_cloud]
    return items


def _read_band(href, bbox_4326, out_shape=None):
    with rasterio.open(href) as src:
        bw, bs, be, bn = transform_bounds("EPSG:4326", src.crs, *bbox_4326)
        win = from_bounds(bw, bs, be, bn, transform=src.transform)
        resampling = Resampling.average if out_shape is not None else Resampling.nearest
        data = src.read(
            1, window=win, boundless=True, fill_value=0,
            out_shape=out_shape, resampling=resampling,
        ).astype(np.float32)
        transform = src.window_transform(win)
        if out_shape is not None:
            sy = (win.height / out_shape[0])
            sx = (win.width / out_shape[1])
            transform = transform * transform.scale(sx, sy)
        return data, transform, src.crs


def load_scene_bands(item, bbox_4326):
    """Load all bands for one scene onto the 20 m (SCL-native) grid.

    Returns (bands dict of name -> reflectance array [0-1] except SCL which
    stays a class code, transform, crs).
    """
    scl, transform, crs = _read_band(item.assets["SCL"].href, bbox_4326)
    target_shape = scl.shape
    bands = {"SCL": scl}
    for b in S2_10M_BANDS:
        raw, _, _ = _read_band(item.assets[b].href, bbox_4326, out_shape=target_shape)
        bands[b] = raw * REFLECTANCE_SCALE
    for b in ["B11", "B12"]:
        raw, _, _ = _read_band(item.assets[b].href, bbox_4326, out_shape=target_shape)
        bands[b] = raw * REFLECTANCE_SCALE
    return bands, transform, crs


def stable_water_mask(scene_band_list, min_fraction=0.5):
    """Water footprint from SCL class 6, majority vote across multiple clear scenes.

    Deliberately not derived from any single scene's SCL (a genuine plume can
    shift how a pixel gets classified on the event day) or from an outside
    bathymetry raster (abd.md assigns Abd the SCL-based derivation, decoupled
    from Pulga's independent bathymetric mask).
    """
    votes = np.stack([(b["SCL"] == SCL_WATER).astype(np.float32) for b in scene_band_list])
    return votes.mean(axis=0) >= min_fraction


def unusable_mask(bands):
    """Cloud / cloud-shadow / nodata / saturated pixels for one scene, from its own SCL."""
    return np.isin(bands["SCL"], list(SCL_UNUSABLE))


def glint_mask(bands, swir_threshold=0.05):
    """Flag likely sun-glint: open water should have near-zero SWIR reflectance;
    glint elevates reflectance broadly, including bands water normally absorbs."""
    return (bands["B11"] > swir_threshold) | (bands["B12"] > swir_threshold)


def spectral_indices(bands):
    """NDSSI, NSMI, red/green ratio, and a plain red-band reflectance value.

    All are computed per-pixel; comparison against a baseline composite is the
    caller's job (see anomaly()).
    """
    blue, green, red, nir = bands["B02"], bands["B03"], bands["B04"], bands["B08"]
    eps = 1e-6
    ndssi = (blue - nir) / (blue + nir + eps)
    nsmi = (red + green - blue) / (red + green + blue + eps)
    red_green_ratio = red / (green + eps)
    return {
        "ndssi": ndssi,
        "nsmi": nsmi,
        "red_green_ratio": red_green_ratio,
        "red_reflectance": red,
    }


def baseline_composite(scene_band_list):
    """Per-band median across clear pre-event scenes, and the matching indices."""
    composite = {}
    for key in S2_ALL_BANDS:
        if key == "SCL":
            continue
        stacked = np.stack([b[key] for b in scene_band_list])
        composite[key] = np.median(stacked, axis=0)
    return composite


def anomaly(baseline_indices, post_indices, valid_mask):
    """post - baseline for each index, masked to valid (water, cloud-free, non-glint) pixels."""
    out = {}
    for key in post_indices:
        diff = post_indices[key] - baseline_indices[key]
        diff = np.where(valid_mask, diff, np.nan)
        out[key] = diff
    return out


def anomaly_to_probability(anomaly_array, low_pct=50, high_pct=99.5):
    """Percentile-stretch an anomaly map to a 0-1 probability-like raster.

    Not a calibrated probability — a monotonic rescaling for visualization and
    thresholding, documented as such per abd.md's requirement to be explicit
    about what the "probability" raster actually represents.
    """
    valid = anomaly_array[~np.isnan(anomaly_array)]
    if valid.size == 0:
        return np.zeros_like(anomaly_array)
    lo, hi = np.percentile(valid, [low_pct, high_pct])
    prob = (anomaly_array - lo) / (hi - lo + 1e-9)
    return np.clip(np.nan_to_num(prob, nan=0.0), 0, 1)


def probability_to_polygons(probability, transform, crs, threshold=0.7, min_pixels=4):
    """Vectorize the probability raster above `threshold` into polygons."""
    mask = (probability >= threshold).astype(np.uint8)
    geoms = []
    for geom, value in raster_shapes(mask, mask=mask.astype(bool), transform=transform):
        if value == 1:
            geoms.append(shape(geom))
    geoms = [g for g in geoms if g.area / (abs(transform.a) * abs(transform.e)) >= min_pixels]
    return geoms, crs
