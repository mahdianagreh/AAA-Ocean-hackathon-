"""Render a predicted plume onto real satellite imagery. Nothing here is generated.

WHAT THIS IS FOR
----------------
The product needs to answer "the model says a flood is coming — where does the mud go?"
with a picture. The tempting shortcut is to generate that picture. A diffusion model has
never seen Aqaba, so it would draw a confident wrong coastline with an invented plume,
and because it would look like satellite imagery it would read as an OBSERVATION. That
is unusable in a project whose validation story is "the satellite could not see the
plume, so we said so and used a mooring instead".

So every pixel here has a provenance:

  background   real Esri WorldImagery, baked offline by scripts/fetch_basemap_raster.py
  plume        the polygons /plume/simulate actually returned
  reef zones   real Allen Coral Atlas v2.0 geometry
  outlet       the surveyed release point

THE CHECK THAT EARNED ITS PLACE
-------------------------------
Plume contours are CLIPPED TO THE SEA. Unclipped, the current synthetic stub returns
concentric circles around the release point with no knowledge of the coastline, and the
first render put the plume over Aqaba's city centre, the airport and a golf course.
Seawater sediment cannot do that.

That is the argument for rendering real data rather than generating an image: a
generated picture would have drawn a plausible coast and hidden the fault entirely.
Real geometry fails visibly. `clip_to_sea=False` exists only so that failure can be
shown deliberately.

OFFLINE
-------
No tile fetch at request time. DoD item 9 is "works with wifi off", and a tile server
hiccup must not present as a broken prediction. If the baked basemap is absent the
render still succeeds on a plain ground and SAYS SO in the footer — a missing basemap is
reported, never faked.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
BASEMAP_DIR = REPO_ROOT / "data" / "processed" / "basemap"
BASEMAP_STEM = "aqaba_marine_esri"

VECTORS = REPO_ROOT / "data" / "processed" / "vectors"
WEB = "EPSG:3857"

#: Plume fill. Ochre, because that is what suspended wadi sediment looks like against
#: the Gulf's blue — the colour is doing information work, not decoration.
PLUME_RGB = "#c8721f"
PLUME_EDGE = "#ffd9a0"
REEF_RGB = "#35e0c8"
OUTLET_RGB = "#ff4d4d"

#: Risk bands per concept §14.5. Kept here so the map and the cards cannot disagree.
RISK_COLOURS = {
    "minimal": "#35e0c8",
    "low": "#8fd744",
    "moderate": "#f2c53d",
    "high": "#ef7d3c",
    "critical": "#d7263d",
}


@dataclass(frozen=True)
class Basemap:
    """A baked satellite image and the ground it covers."""

    path: Path
    left: float
    right: float
    bottom: float
    top: float
    attribution: str
    fetched_utc: str

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """matplotlib's imshow order: left, right, bottom, top."""
        return (self.left, self.right, self.bottom, self.top)


def load_basemap(directory: Path | None = None) -> Basemap | None:
    """The baked basemap, or None when it has not been fetched.

    None is a legitimate state, not an error: a fresh clone has no basemap because the
    file is derived and git-ignored. The caller renders without it and says so.
    """
    directory = directory or BASEMAP_DIR
    meta_path = directory / f"{BASEMAP_STEM}.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    image = directory / meta.get("image", f"{BASEMAP_STEM}.jpg")
    if not image.exists():
        return None
    return Basemap(
        path=image,
        left=float(meta["left"]), right=float(meta["right"]),
        bottom=float(meta["bottom"]), top=float(meta["top"]),
        attribution=meta.get("attribution", "Esri WorldImagery"),
        fetched_utc=meta.get("fetched_utc", "unknown"),
    )


def _sea_polygon():
    """Union of the water layer, in Web Mercator. None if the coastline is absent."""
    import geopandas as gpd

    path = VECTORS / "coastline.gpkg"
    if not path.exists():
        return None
    return gpd.read_file(path, layer="water").to_crs(WEB).union_all()


def contours_to_frame(contours: Sequence[dict[str, Any]], *, clip_to_sea: bool = True):
    """Plume contours -> GeoDataFrame in Web Mercator, clipped to the sea.

    `contours` is the payload from `/plume/simulate`: each item carries `t_hours`,
    `probability` and a GeoJSON `geometry` in EPSG:4326.
    """
    import geopandas as gpd
    from shapely.geometry import shape

    if not contours:
        return gpd.GeoDataFrame({"t_hours": [], "probability": []},
                                geometry=[], crs=WEB)

    frame = gpd.GeoDataFrame(
        {"t_hours": [float(c["t_hours"]) for c in contours],
         "probability": [float(c["probability"]) for c in contours]},
        geometry=[shape(c["geometry"]) for c in contours],
        crs="EPSG:4326",
    ).to_crs(WEB)

    if clip_to_sea:
        sea = _sea_polygon()
        if sea is not None:
            frame["geometry"] = frame.geometry.intersection(sea)
            frame = frame[~frame.geometry.is_empty].copy()

    return frame.sort_values("t_hours").reset_index(drop=True)


def _reef_zones(exposure_by_zone: dict[str, dict] | None):
    """Reef zones in Web Mercator, with the risk level attached where one exists."""
    import geopandas as gpd

    path = VECTORS / "reef_zones.gpkg"
    if not path.exists():
        return None
    zones = gpd.read_file(path).to_crs(WEB)
    exposure_by_zone = exposure_by_zone or {}
    zones["risk_level"] = zones["reef_zone_id"].map(
        lambda z: (exposure_by_zone.get(z) or {}).get("risk_level"))
    zones["risk_score"] = zones["reef_zone_id"].map(
        lambda z: (exposure_by_zone.get(z) or {}).get("risk_score"))
    return zones


def render(
    contours: Sequence[dict[str, Any]],
    *,
    event_id: str,
    outlet_id: str,
    horizon_hours: float,
    exposure_by_zone: dict[str, dict] | None = None,
    upto_hours: float | None = None,
    clip_to_sea: bool = True,
    width_px: int = 1100,
    dpi: int = 130,
) -> bytes:
    """Return a PNG of the plume over real imagery.

    `upto_hours` draws only contours at or before that time, which is how the animation
    frames are produced — one call per timestep, same extent every time so the frames
    register against each other.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    import geopandas as gpd

    # The FULL contour set frames the view; `upto_hours` only controls what is drawn.
    # Framing on the visible subset instead would rescale every animation frame, and a
    # plume that grows would appear not to move at all.
    everything = contours_to_frame(contours, clip_to_sea=clip_to_sea)
    plume = everything
    if upto_hours is not None:
        plume = everything[everything["t_hours"] <= float(upto_hours)]

    basemap = load_basemap()
    zones = _reef_zones(exposure_by_zone)

    if not everything.empty:
        minx, miny, maxx, maxy = everything.total_bounds
        # Include any reef zone the plume actually touches, so the thing at risk is in
        # frame beside the thing threatening it.
        if zones is not None and not zones.empty:
            hit = zones[zones.intersects(everything.union_all())]
            if not hit.empty:
                zminx, zminy, zmaxx, zmaxy = hit.total_bounds
                minx, miny = min(minx, zminx), min(miny, zminy)
                maxx, maxy = max(maxx, zmaxx), max(maxy, zmaxy)
        pad = max(maxx - minx, maxy - miny) * 0.45
        left, right = minx - pad, maxx + pad
        bottom, top = miny - pad, maxy + pad
        # Never ask for ground the baked image does not cover — outside it there is
        # simply nothing to draw, and the frame would show blank instead of coast.
        if basemap is not None:
            left, right = max(left, basemap.left), min(right, basemap.right)
            bottom, top = max(bottom, basemap.bottom), min(top, basemap.top)
    elif basemap is not None:
        left, right, bottom, top = basemap.extent
    else:
        from config.spatial import MARINE_AOI  # noqa: PLC0415

        box = gpd.GeoSeries.from_wkt(
            [f"POLYGON(({MARINE_AOI.west} {MARINE_AOI.south}, "
             f"{MARINE_AOI.east} {MARINE_AOI.south}, "
             f"{MARINE_AOI.east} {MARINE_AOI.north}, "
             f"{MARINE_AOI.west} {MARINE_AOI.north}, "
             f"{MARINE_AOI.west} {MARINE_AOI.south}))"], crs="EPSG:4326").to_crs(WEB)
        left, bottom, right, top = box.total_bounds

    aspect = (top - bottom) / (right - left) if right > left else 1.0
    fig_w = width_px / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * aspect), dpi=dpi)

    if basemap is not None:
        from PIL import Image

        with Image.open(basemap.path) as im:
            ax.imshow(im, extent=basemap.extent, origin="upper", zorder=0,
                      interpolation="bilinear")
        ground = f"Esri WorldImagery, baked {basemap.fetched_utc[:10]}"
    else:
        ax.set_facecolor("#0d2b3a")
        ground = ("NO BASEMAP — run scripts/fetch_basemap_raster.py. "
                  "Geometry is real; the background is blank, not imagery")

    # Newest contour last so the tight early one stays legible on top of the wide ones.
    order = plume.sort_values("t_hours", ascending=False)
    n = max(len(order) - 1, 1)
    for i, (_, row) in enumerate(order.iterrows()):
        # Drawn through geopandas rather than matplotlib.Polygon: clipping to the coast
        # turns a circle into a MultiPolygon, which has no .exterior.
        gpd.GeoSeries([row.geometry], crs=WEB).plot(
            ax=ax, facecolor=PLUME_RGB, edgecolor=PLUME_EDGE,
            alpha=0.16 + 0.5 * (i / n), linewidth=1.0, zorder=3)

    if zones is not None and not zones.empty:
        for _, r in zones.iterrows():
            colour = RISK_COLOURS.get(r["risk_level"] or "", REEF_RGB)
            gpd.GeoSeries([r.geometry], crs=WEB).plot(
                ax=ax, facecolor="none", edgecolor=colour, linewidth=2.0, zorder=4)
        import pandas as pd

        for _, r in zones.iterrows():
            c = r.geometry.centroid
            label = r["reef_zone_id"]
            # pandas .map over missing keys yields NaN, not None, so `is not None` was
            # true and every unscored zone rendered as "R-02 · nan" on the image.
            if pd.notna(r["risk_score"]):
                label = f"{label} · {float(r['risk_score']):.0f}"
            ax.annotate(label, (c.x, c.y), xytext=(8, 0), textcoords="offset points",
                        fontsize=7.5, weight="bold",
                        color=RISK_COLOURS.get(r["risk_level"] or "", REEF_RGB),
                        va="center", zorder=5)

    outlets_path = VECTORS / "outlets.geojson"
    if outlets_path.exists():
        outlets = gpd.read_file(outlets_path).to_crs(WEB)
        here = outlets[outlets["outlet_id"] == outlet_id]
        if not here.empty:
            here.plot(ax=ax, color=OUTLET_RGB, markersize=110, marker="v",
                      edgecolor="white", linewidth=1.3, zorder=6)
            p = here.geometry.iloc[0]
            ax.annotate(outlet_id, (p.x, p.y), xytext=(12, -14),
                        textcoords="offset points", fontsize=8, weight="bold",
                        color="white", zorder=7,
                        bbox=dict(boxstyle="round,pad=0.28", fc="#c0392b", alpha=0.9))

    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    ax.set_xticks([]); ax.set_yticks([])

    shown = f"+{upto_hours:.0f} h" if upto_hours is not None else f"to +{horizon_hours:.0f} h"
    ax.set_title(f"Predicted sediment plume · {event_id} · released at {outlet_id}\n{shown}",
                 fontsize=11, weight="bold", pad=9)

    handles = [Patch(facecolor=PLUME_RGB, alpha=0.55,
                     label="plume probability (darker = arrives sooner)")]
    if zones is not None and not zones.empty:
        handles.append(Patch(facecolor="none", edgecolor=REEF_RGB, linewidth=2,
                             label="reef zones (Allen Coral Atlas v2.0)"))
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, framealpha=0.86)

    # Dark on the white figure margin. This was near-white, chosen for a dark basemap —
    # but the footer sits OUTSIDE the axes, on the figure background, so it rendered
    # almost invisible. This line is the whole honesty mechanism: it is what tells a
    # reader who screenshots the image into a slide that the plume is model output and
    # the background is a real photograph. An unreadable provenance note is no
    # provenance note.
    fig.text(0.5, 0.008,
             f"Background: {ground}.  Plume: model output.  "
             f"Reef: real ACA geometry.  No part of this image is generated.",
             ha="center", fontsize=6.8, color="#2b3a42")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.06,
                facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def frame_times(contours: Iterable[dict[str, Any]]) -> list[float]:
    """Timesteps available to animate, ascending."""
    return sorted({float(c["t_hours"]) for c in contours})
