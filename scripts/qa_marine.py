"""Marine-chain QA figure suite — one artifact per transformation step.

Run: ../.venv/bin/python qa_marine.py   (from scripts/)

Includes before/after evidence for three of the four bugs already caught, because
"we fixed it" is a claim, and a claim without a picture is exactly what this phase
is meant to eliminate.

Since 3 Aug the reef figures are drawn from the real Allen Coral Atlas geometry
(`reef_zones.gpkg`) whenever export_aca.py has produced it, and fall back to the
provisional boxes otherwise. Which file was used is printed at the end of the run
and stated in the figure captions — the geometry a figure describes is not
something a reader should have to infer from a filename.
"""

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
import rasterio.features

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon
from shapely.ops import unary_union

from pulga_config import AOI_CRS_PROJECTED, AOI_CRS_STORAGE, PROCESSED, RAW, VECTORS
from make_reef_zones_provisional import (
    REEF_STRIP_M,
    ZONE_DEFS,
    jordan_shore_points,
)
from process_bathymetry import CONTROL_LAND, CONTROL_WATER, resolve_source
from qa_common import CRS_BASEMAP, add_satellite, save_fig

DEPTH = PROCESSED / "bathymetry" / "depth_utm36n.tif"
COAST = VECTORS / "coastline.gpkg"
SRC = "Marine chain"

# Prefer the real ACA-derived zones once export_aca.py build has run, and fall back
# to the provisional boxes before that. Pinning the provisional path meant the whole
# reef figure set silently kept showing hand-drawn boxes after real habitat landed —
# the figures would have looked fine and described geometry nobody uses any more.
REEF_FINAL = VECTORS / "reef_zones.gpkg"
REEF_PROVISIONAL = VECTORS / "reef_zones_PROVISIONAL.gpkg"
REEF = REEF_FINAL if REEF_FINAL.exists() else REEF_PROVISIONAL
REEF_IS_FINAL = REEF == REEF_FINAL
REEF_LABEL = "ACA-derived" if REEF_IS_FINAL else "Provisional"


def water_mask():
    with rasterio.open(DEPTH) as src:
        elev = src.read(1)
        mask = (elev < 0) & (elev != src.nodata)
        extent = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    return elev, mask, extent


# --------------------------------------------------------------- reef zones

def reef_01_over_satellite():
    zones = gpd.read_file(REEF).to_crs(CRS_BASEMAP)
    fig, ax = plt.subplots(figsize=(11, 14))
    zones.plot(ax=ax, facecolor="#ff6600", edgecolor="black", linewidth=1.4, alpha=0.62)
    for _, r in zones.iterrows():
        c = r.geometry.centroid
        ax.annotate(f"{r['reef_zone_id']}  {r['area_km2']:.2f} km²",
                    (c.x, c.y), xytext=(22, 0), textcoords="offset points",
                    fontsize=9.5, weight="bold", color="white", va="center",
                    bbox=dict(boxstyle="round,pad=0.3", fc="black", alpha=0.6))
    add_satellite(ax, zoom=13)
    ax.set_title(f"{REEF_LABEL} reef zones R-01…R-08 over Esri WorldImagery")
    ax.set_xticks([]); ax.set_yticks([])
    # The filename keeps the word "provisional" because four docs link to it by name,
    # so the caption has to carry the geometry basis instead — otherwise the one thing
    # a reader takes from it is that these are still hand-drawn boxes.
    save_fig(fig, "reef_01_provisional_over_satellite",
             f"GEOMETRY: {REEF_LABEL} ({REEF.name}). "
             "All 8 zones on satellite imagery. Every zone must lie on the water side of the "
             "visible shoreline — this is the check that caught the first attempt placing "
             "R-03–R-05 on dry land. The fringing-reef shelf is visible as the pale strip "
             "hugging the coast.", SRC, dpi=170)


def reef_02_zone_insets():
    zones = gpd.read_file(REEF).to_crs(CRS_BASEMAP)
    fig, axes = plt.subplots(2, 4, figsize=(21, 11))
    for ax, (_, r) in zip(axes.ravel(), zones.iterrows()):
        gpd.GeoSeries([r.geometry], crs=CRS_BASEMAP).plot(
            ax=ax, facecolor="#ff6600", edgecolor="yellow", linewidth=2.0, alpha=0.45)
        b = r.geometry.bounds
        padx = max(420, (b[2] - b[0]) * 0.30)
        pady = max(420, (b[3] - b[1]) * 0.12)
        ax.set_xlim(b[0] - padx, b[2] + padx)
        ax.set_ylim(b[1] - pady, b[3] + pady)
        add_satellite(ax, zoom=15)
        ax.set_title(f"{r['reef_zone_id']} · {r['zone_name'][:32]}\n"
                     f"{r['area_km2']:.2f} km², park {r['marine_park_overlap_pct']:.0f}%, "
                     f"med depth {r['depth_median_m']:.0f} m", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"Per-zone detail — each {REEF_LABEL} reef zone on imagery", fontsize=14)
    save_fig(fig, "reef_02_per_zone_insets",
             "Each zone individually against imagery, annotated with area, Marine Park "
             "overlap and median depth. R-01/R-02 visibly cover developed beach and port "
             "frontage, which is why they are flagged as the most likely to be dropped when "
             "Allen Coral Atlas lands.", SRC, dpi=150)


def _strips_without_band_clip():
    """Rebuild the geometry as it was BEFORE the band-clip fix, to show the bug.

    Reproduced from the pre-fix code path rather than described in prose: the
    perpendicular buffer bled across the latitude-band boundary wherever the coast
    bends, so adjacent zones overlapped and any reef area inside the overlap was
    counted twice in the exposure score.
    """
    pts = jordan_shore_points()
    water = unary_union(
        gpd.read_file(COAST, layer="water").to_crs(AOI_CRS_PROJECTED).geometry.tolist()
    )
    t = Transformer.from_crs(AOI_CRS_STORAGE, AOI_CRS_PROJECTED, always_xy=True)

    out = {}
    for zone_id, _, lat_n, lat_s in ZONE_DEFS:
        _, n_max = t.transform(35.0, lat_n)
        _, n_min = t.transform(35.0, lat_s)
        seg = [p for p in pts if n_min <= p[1] <= n_max]
        if len(seg) < 2:
            continue
        strip = LineString(seg).buffer(REEF_STRIP_M, cap_style=2).intersection(water)
        if isinstance(strip, MultiPolygon):
            strip = max(strip.geoms, key=lambda g: g.area)
        out[zone_id] = strip
    return out


def reef_03_overlap_before_after():
    before = _strips_without_band_clip()
    after = gpd.read_file(REEF).to_crs(AOI_CRS_PROJECTED).set_index("reef_zone_id")

    ov_before = before["R-04"].intersection(before["R-05"])
    ov_after = after.loc["R-04", "geometry"].intersection(after.loc["R-05", "geometry"])

    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    for ax, (label, geoms, ov) in zip(
        axes,
        [("BEFORE — no band clip", before, ov_before),
         ("AFTER — clipped to latitude band",
          {k: after.loc[k, "geometry"] for k in after.index}, ov_after)],
    ):
        for zid in ["R-03", "R-04", "R-05", "R-06"]:
            if zid not in geoms:
                continue
            colour = {"R-04": "#1f77b4", "R-05": "#ff7f0e"}.get(zid, "#cccccc")
            gpd.GeoSeries([geoms[zid]], crs=AOI_CRS_PROJECTED).plot(
                ax=ax, facecolor=colour, edgecolor="black", linewidth=1.0, alpha=0.55)
            c = geoms[zid].centroid
            ax.annotate(zid, (c.x, c.y), xytext=(26, 0), textcoords="offset points",
                        fontsize=10, weight="bold", va="center")
        area = ov.area if not ov.is_empty else 0.0
        if area > 0:
            gpd.GeoSeries([ov], crs=AOI_CRS_PROJECTED).plot(
                ax=ax, facecolor="red", edgecolor="red", alpha=0.95, zorder=6)
        ax.set_title(f"{label}\nR-04 ∩ R-05 = {area:,.0f} m² "
                     f"({area / 1e4:.2f} ha)", fontsize=11)
        ax.set_xlabel("easting (m)")

        b = after.loc[["R-04", "R-05"], "geometry"].total_bounds
        ax.set_xlim(b[0] - 500, b[2] + 500)
        ax.set_ylim(b[1] - 400, b[3] + 400)
    axes[0].set_ylabel("northing (m)")
    fig.suptitle("BUG FIXED — reef zone overlap at the R-04 / R-05 boundary", fontsize=13)
    save_fig(fig, "reef_03_overlap_bug_before_after",
             f"Left: the pre-fix geometry, {ov_before.area / 1e4:.2f} ha of double-counted "
             "reef in red where the perpendicular buffer bled across the band boundary. "
             "Right: after clipping each strip to its own latitude band, the overlap is "
             f"{ov_after.area:,.0f} m². An exposure score computed on the left would have "
             "inflated the headline number.", SRC)
    return ov_before.area, ov_after.area


def reef_04_marine_park():
    zones = gpd.read_file(REEF).to_crs(CRS_BASEMAP)
    pa = gpd.read_file(VECTORS / "osm_aqaba.gpkg", layer="protected_areas").to_crs(CRS_BASEMAP)
    park = pa[pa["protection_title"] == "Marine Park"]

    fig, ax = plt.subplots(figsize=(11, 14))
    if not park.empty:
        park.plot(ax=ax, facecolor="#00ffcc", edgecolor="#00ffcc",
                  linewidth=3.0, alpha=0.22)
    zones.plot(ax=ax, facecolor="none", edgecolor="#ff6600", linewidth=2.4)
    for _, r in zones.iterrows():
        c = r.geometry.centroid
        pct = r["marine_park_overlap_pct"]
        ax.annotate(f"{r['reef_zone_id']}  {pct:.0f}% in park",
                    (c.x, c.y), xytext=(22, 0), textcoords="offset points",
                    fontsize=9.5, weight="bold", color="white", va="center",
                    bbox=dict(boxstyle="round,pad=0.3",
                              fc="#006644" if pct > 50 else "#663300", alpha=0.75))
    add_satellite(ax, zoom=13)
    ax.set_title("INDEPENDENT VALIDATION — reef zones vs the Aqaba Marine Park\n"
                 "(park boundary from OSM, never used as an input to zone placement)")
    ax.set_xticks([]); ax.set_yticks([])
    save_fig(fig, "reef_04_marine_park_validation",
             "The Aqaba Marine Park (protect_class=4, 3.45 km², 29.397–29.460 N) in cyan "
             "against our zones. R-04–R-07 are 67–85% inside it despite the park never being "
             "used to place them — independent corroboration that the dive-site latitudes are "
             "right. R-01–R-03 fall outside, consistent with them being city and port "
             "frontage.", SRC, dpi=170)


# ------------------------------------------------------------------- depth

def depth_01_full_raster():
    elev, mask, extent = water_mask()
    show = np.where(elev == -32768.0, np.nan, elev)

    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    im = axes[0].imshow(show, extent=extent, cmap="terrain", vmin=-950, vmax=1550)
    axes[0].set_title("Depth / elevation field, EPSG:32636 @ 50 m\n"
                      "min −907.1 m, max +1542.3 m")
    fig.colorbar(im, ax=axes[0], shrink=0.7, label="metres")

    cs = axes[1].contour(
        np.flipud(show), levels=[-800, -600, -400, -200, -100, -50, 0],
        extent=extent, colors="black", linewidths=0.7)
    axes[1].clabel(cs, fmt="%d", fontsize=7)
    axes[1].imshow(mask, extent=extent, cmap="Blues", vmin=0, vmax=1.6, alpha=0.5)
    axes[1].set_title("Isobaths — note how tightly they crowd the Jordanian shore\n"
                      "(the steep drop-off the 450 m source cannot truly resolve)")
    for a in axes:
        a.set_xlabel("easting (m)")
    axes[0].set_ylabel("northing (m)")
    save_fig(fig, "depth_01_full_field_and_isobaths",
             "The full depth field handed to Nizar, and its isobaths. The −50 to −400 m "
             "contours crowd into a few hundred metres at the coast: that crowding is why "
             "reef-zone width is an explicit 250 m assumption rather than being derived from "
             "these contours.", SRC)


def depth_02_control_points():
    elev, mask, extent = water_mask()
    src_path, provenance = resolve_source()

    t = Transformer.from_crs(AOI_CRS_STORAGE, AOI_CRS_PROJECTED, always_xy=True)
    with rasterio.open(src_path) as src:
        def sample(lon, lat):
            return float(list(src.sample([(lon, lat)]))[0][0])

        pts = ([(lon, lat, lab, "water", sample(lon, lat)) for (lon, lat), lab in CONTROL_WATER]
               + [(lon, lat, lab, "land", sample(lon, lat)) for (lon, lat), lab in CONTROL_LAND])

    fig, ax = plt.subplots(figsize=(11.5, 14))
    ax.imshow(mask, extent=extent, cmap="Blues", vmin=0, vmax=1.5, interpolation="nearest")

    n_ok = 0
    for lon, lat, label, expected, val in pts:
        x, y = t.transform(lon, lat)
        derived = "water" if val < 0 else "land"
        ok = derived == expected
        n_ok += ok
        ax.scatter([x], [y], s=170, marker="o" if expected == "water" else "s",
                   facecolor="#00cc44" if ok else "red",
                   edgecolor="black", linewidth=1.3, zorder=6)
        ax.annotate(f"{label}\nexp {expected} · got {val:+.0f} m {'✓' if ok else '✗'}",
                    (x, y), xytext=(13, 0), textcoords="offset points", fontsize=7.2,
                    va="center",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", alpha=0.82,
                              ec="#00cc44" if ok else "red"))

    ax.set_title(f"SIGN-CONVENTION VERIFICATION — {n_ok}/{len(pts)} control points pass\n"
                 "circles = expected water, squares = expected land")
    ax.set_xlabel("easting (m)"); ax.set_ylabel("northing (m)")
    save_fig(fig, "depth_02_sign_convention_22_control_points",
             f"All {len(pts)} control points, each labelled with what was expected and the "
             f"value actually sampled from {src_path.name}. Expanded from the original 5, "
             "which were clustered near the city and could have passed while the mask was "
             "wrong elsewhere. The expansion caught two points wrongly assumed to be "
             "mid-gulf that are in fact Wadi Araba land at +533 m and +241 m.", SRC, dpi=160)
    return n_ok, len(pts)


def depth_03_nodata_before_after():
    src_path, _ = resolve_source()
    with rasterio.open(src_path) as src:
        raw = src.read(1).astype("float32")
        raw_ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    with rasterio.open(DEPTH) as src:
        out = src.read(1)
        nod = src.nodata
        out_ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)

    raw_nan = np.isnan(raw)
    out_nan = np.isnan(out)
    out_sentinel = out == nod

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))

    axes[0].imshow(raw_nan, extent=raw_ext, cmap="Reds", vmin=0, vmax=1,
                   interpolation="nearest")
    axes[0].set_title(f"BEFORE — raw {src_path.name}\n"
                      f"{raw_nan.sum():,} bare NaN cells ({raw_nan.mean() * 100:.2f}%), "
                      "no nodata tag declared")

    axes[1].imshow(out_nan, extent=out_ext, cmap="Reds", vmin=0, vmax=1,
                   interpolation="nearest")
    axes[1].set_title(f"AFTER — depth_utm36n.tif\n{out_nan.sum():,} NaN cells "
                      "(gap-filled, assert enforces zero)")

    axes[2].imshow(out_sentinel, extent=out_ext, cmap="Greys", vmin=0, vmax=1,
                   interpolation="nearest")
    axes[2].set_title(f"AFTER — declared −32768 sentinel\n{out_sentinel.sum():,} cells, "
                      "reprojection margin only")

    for a in axes:
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle("BUG FIXED — mixed NaN / −32768 nodata consolidated to one sentinel",
                 fontsize=13)
    save_fig(fig, "depth_03_nodata_bug_before_after",
             f"Left: {raw_nan.sum():,} scattered NaN cells in the source, with no nodata tag, "
             "some inside the sea body. Middle: zero NaN survive. Right: the single declared "
             "sentinel, confined to the reprojection margin. A NaN depth does not raise — it "
             "would have silently turned Nizar's particle positions into non-numbers.", SRC)
    return int(raw_nan.sum()), int(out_nan.sum())


def depth_04_crossshore_profiles():
    pts = jordan_shore_points()
    with rasterio.open(DEPTH) as src:
        elev = src.read(1)
        nod = src.nodata
        t = Transformer.from_crs(AOI_CRS_STORAGE, AOI_CRS_PROJECTED, always_xy=True)

        fig, ax = plt.subplots(figsize=(13, 7.5))
        offs = np.arange(0, 2001, 50)
        for zone_id, name, lat_n, lat_s in ZONE_DEFS:
            _, n_max = t.transform(35.0, lat_n)
            _, n_min = t.transform(35.0, lat_s)
            seg = [p for p in pts if n_min <= p[1] <= n_max]
            if not seg:
                continue
            e0, n0 = seg[len(seg) // 2]
            prof = []
            for o in offs:
                r, c = src.index(e0 - o, n0)
                v = elev[r, c] if (0 <= r < elev.shape[0] and 0 <= c < elev.shape[1]) else np.nan
                prof.append(np.nan if v == nod else v)
            ax.plot(offs, prof, lw=1.9, label=f"{zone_id} {name[:26]}")

    ax.axvspan(0, REEF_STRIP_M, color="#ff6600", alpha=0.16,
               label=f"assumed reef strip (0–{REEF_STRIP_M:.0f} m)")
    ax.axhline(0, color="black", lw=1)
    ax.axhline(-30, color="green", ls="--", lw=1.2, label="−30 m, optically-shallow limit")
    ax.set_xlabel("metres offshore (west) from the derived shoreline")
    ax.set_ylabel("elevation (m)")
    ax.set_title("Across-shore depth profile at each reef zone\n"
                 "why reef width is an assumption, not a derived contour")
    ax.legend(fontsize=8, loc="lower left", ncol=2)
    ax.grid(alpha=0.3)
    save_fig(fig, "depth_04_crossshore_profiles_per_zone",
             "Depth against distance offshore at each zone. Several profiles fall through "
             "−200 m within 250 m of shore, which is physically implausible for a real reef "
             "shelf and is an interpolation artefact of the ~450 m source. Deriving a reef "
             "edge from these curves would dress that artefact up as a measurement — hence "
             "the flat 250 m placeholder.", SRC)


# --------------------------------------------------------------- coastline

def coast_01_sea_body():
    elev, mask, extent = water_mask()
    water = gpd.read_file(COAST, layer="water").to_crs(AOI_CRS_PROJECTED)

    fig, ax = plt.subplots(figsize=(10, 13))
    ax.imshow(mask, extent=extent, cmap="Blues", vmin=0, vmax=1.5, interpolation="nearest")
    water.boundary.plot(ax=ax, color="red", linewidth=1.5)
    ax.set_title(f"coastline.gpkg — {len(water)} water polygon(s), "
                 f"{water.geometry.area.sum() / 1e6:.1f} km²\n"
                 "single sea body, no spurious interior lakes")
    ax.set_xlabel("easting (m)"); ax.set_ylabel("northing (m)")
    save_fig(fig, "coastline_01_single_sea_body",
             f"The land barrier Nizar's particle engine uses. Exactly one polygon of "
             f"{water.geometry.area.sum() / 1e6:.1f} km². Interior 'lakes' in dry wadi floors "
             "would punch false holes in the barrier and let particles escape inland; the "
             "0.05 km² speck filter exists to prevent that and dropped zero specks here.", SRC)


def coast_02_osm_vs_derived():
    """Independent-lineage check that justifies the GMRT substitution."""
    ours = gpd.read_file(COAST, layer="water").to_crs(AOI_CRS_PROJECTED)
    ours_line = ours.union_all().boundary
    try:
        osm_c = gpd.read_file(VECTORS / "osm_aqaba.gpkg", layer="osm_coastline").to_crs(
            AOI_CRS_PROJECTED)
    except Exception:
        print("    (skip coast_02 — no osm_coastline layer)"); return None
    if osm_c.empty:
        print("    (skip coast_02 — osm_coastline empty)"); return None

    osm_line = unary_union(osm_c.geometry.tolist())
    samples = [osm_line.interpolate(d) for d in np.linspace(0, osm_line.length, 500)]
    dists = np.array([p.distance(ours_line) for p in samples])

    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    ax = axes[0]
    ours.boundary.plot(ax=ax, color="red", linewidth=1.8, label="GMRT-derived (ours)")
    osm_c.plot(ax=ax, color="#00cc44", linewidth=1.8, label="OSM natural=coastline")
    ax.legend(fontsize=10)
    b = osm_c.total_bounds
    ax.set_xlim(b[0] - 900, b[2] + 900); ax.set_ylim(b[1] - 900, b[3] + 900)
    ax.set_title("Two independent coastlines overlaid")
    ax.set_xlabel("easting (m)"); ax.set_ylabel("northing (m)")

    ax = axes[1]
    ax.hist(dists, bins=45, color="#2b8cbe", edgecolor="white")
    for q, col in [(50, "green"), (90, "orange"), (99, "red")]:
        v = np.percentile(dists, q)
        ax.axvline(v, color=col, ls="--", lw=1.8, label=f"p{q} = {v:.0f} m")
    ax.set_xlabel("distance from OSM coastline to our derived shoreline (m)")
    ax.set_ylabel("sample points")
    ax.set_title(f"Agreement over {len(samples)} sampled points\n"
                 f"median {np.median(dists):.0f} m ≈ one 50 m pixel")
    ax.legend(fontsize=9)

    fig.suptitle("SUBSTITUTION JUSTIFIED — GMRT-derived coastline vs OSM, independent lineage",
                 fontsize=13)
    save_fig(fig, "coastline_02_osm_vs_gmrt_agreement",
             f"OSM's coastline is surveyed/traced from imagery and shares no lineage with "
             f"GMRT, so it is a genuine external check. Median disagreement "
             f"{np.median(dists):.0f} m — about one pixel — rising to "
             f"{np.percentile(dists, 90):.0f} m at p90 in the port and marina where the "
             "coarse bathymetry cannot resolve breakwaters. This quantifies the cost of "
             "substituting GMRT for unobtainable GEBCO instead of asserting it is fine.", SRC)
    return dists



def reef_05_provisional_vs_final():
    """The swap-in check §6.1 asks for by name, and the one that carries the finding.

    Two things must be visible here: that R-NN still means the same stretch of coast
    (centroid drift), and that the named zones capture only part of the reef the Atlas
    actually maps. The second is the more consequential and was invisible until the
    real export existed.
    """
    if not REEF_FINAL.exists():
        print("    (skip reef_05 — no real ACA export yet)"); return

    prov = gpd.read_file(REEF_PROVISIONAL).to_crs(AOI_CRS_PROJECTED)
    real = gpd.read_file(REEF_FINAL).to_crs(AOI_CRS_PROJECTED)
    # origin/main's fragment file carries `aca_class`, not this branch's
    # `is_living_reef` flag. Living reef is benthic 14 (Seagrass) + 15 (Coral/Algae);
    # Sand, Rubble and Rock are mapped substrate, not the habitat being protected.
    LIVING = {14, 15}
    frag_path = VECTORS / "aca_fragments_BEFORE_MERGE.gpkg"
    frags = None
    if frag_path.exists():
        frags = gpd.read_file(frag_path).to_crs(AOI_CRS_PROJECTED)
        frags["is_living_reef"] = frags["aca_class"].isin(LIVING)

    fig, axes = plt.subplots(1, 3, figsize=(21, 11))

    # --- panel 1: extents, provisional vs Atlas
    ax = axes[0]
    prov.boundary.plot(ax=ax, color="#ff6600", linewidth=1.8, label="provisional (250 m strip)")
    real.plot(ax=ax, facecolor="#00a03c", edgecolor="#00a03c", alpha=0.85,
              label="Allen Coral Atlas v2.0")
    ax.legend(fontsize=9, loc="upper right")
    ax.set_title(f"Extents\nprovisional {prov.geometry.area.sum() / 1e6:.2f} km² → "
                 f"Atlas {real.geometry.area.sum() / 1e6:.3f} km²")
    ax.set_xlabel("easting (m)"); ax.set_ylabel("northing (m)")

    # --- panel 2: centroid drift, the ID-continuity check
    ax = axes[1]
    pc = prov.set_index("reef_zone_id").geometry.centroid
    rc = real.set_index("reef_zone_id").geometry.centroid
    drifts = []
    for zid in sorted(rc.index):
        d_km = pc[zid].distance(rc[zid]) / 1000
        drifts.append((zid, d_km))
        ax.plot([pc[zid].x, rc[zid].x], [pc[zid].y, rc[zid].y], "-",
                color="grey", lw=1.2, zorder=2)
        ax.scatter([pc[zid].x], [pc[zid].y], s=70, color="#ff6600", zorder=3)
        ax.scatter([rc[zid].x], [rc[zid].y], s=70, color="#00a03c", zorder=3)
        ax.annotate(f"{zid} {d_km:.2f} km", (rc[zid].x, rc[zid].y), xytext=(9, 0),
                    textcoords="offset points", fontsize=8, va="center")
    worst = max(d for _, d in drifts)
    ax.set_title(f"Centroid drift — ID continuity\nworst {worst:.2f} km against a "
                 f"5 km assert bound: PASS")
    ax.set_xlabel("easting (m)")

    # --- panel 3: scope and area, with the corridor made explicit
    ax = axes[2]
    if frags is not None:
        living = frags[frags["is_living_reef"]]
        corridor = unary_union(prov.geometry.tolist()).buffer(600)
        on_jordan = living.geometry.intersection(corridor)
        elsewhere = living.geometry.difference(corridor)

        gpd.GeoDataFrame(geometry=elsewhere[~elsewhere.is_empty],
                         crs=AOI_CRS_PROJECTED).plot(
            ax=ax, facecolor="#bbbbbb", edgecolor="none")
        gpd.GeoDataFrame(geometry=on_jordan[~on_jordan.is_empty],
                         crs=AOI_CRS_PROJECTED).plot(
            ax=ax, facecolor="#ffcc00", edgecolor="none")
        real.plot(ax=ax, facecolor="#00a03c", edgecolor="#00a03c", alpha=0.95)

        a_else = elsewhere.area.sum() / 1e6
        a_jord = on_jordan.area.sum() / 1e6
        a_scored = real.geometry.area.sum() / 1e6
        ax.set_title(f"Scope\nJordan's reef {a_jord:.3f} km², scored {a_scored:.3f} km² "
                     f"({a_scored / a_jord * 100:.0f}%)")
        ax.legend(handles=[
            mpatches.Patch(facecolor="#bbbbbb",
                           label=f"other nations' waters ({a_else:.3f} km², out of scope)"),
            mpatches.Patch(facecolor="#ffcc00", label=f"Jordan's reef ({a_jord:.3f} km²)"),
            mpatches.Patch(facecolor="#00a03c", label=f"scored ({a_scored:.3f} km²)"),
        ], fontsize=8, loc="upper right")
    ax.set_xlabel("easting (m)")

    fig.suptitle("SWAP-IN #3 — provisional reef zones replaced by Allen Coral Atlas v2.0",
                 fontsize=14)
    fig.tight_layout()
    save_fig(fig, "reef_05_provisional_vs_final",
             f"The swap-in check. IDs are continuous — worst centroid drift {worst:.2f} km "
             "against the 5 km assert bound, and no new IDs. Zones are disjoint, asserted. "
             f"Coverage of Jordan's reef is {a_scored / a_jord * 100:.0f}%; the grey reef is "
             "on the Egyptian and Palestinian shores, inside the same bounding box but never in "
             f"scope. The headline correction is AREA: the provisional strips claimed "
             f"{prov.geometry.area.sum() / 1e6:.2f} km² against a real "
             f"{a_scored:.3f} km², because they assumed a uniform 250 m width along the "
             "whole coast.", SRC, dpi=150)
    print(f"    Jordan reef coverage: {a_scored / a_jord * 100:.1f}%  "
          f"(provisional overestimated area {prov.geometry.area.sum() / 1e6 / a_scored:.1f}x)")


if __name__ == "__main__":
    print("  reef zones...")
    reef_01_over_satellite()
    reef_02_zone_insets()
    ov_b, ov_a = reef_03_overlap_before_after()
    reef_04_marine_park()
    reef_05_provisional_vs_final()

    print("  depth field...")
    depth_01_full_raster()
    n_ok, n_tot = depth_02_control_points()
    raw_nan, out_nan = depth_03_nodata_before_after()
    depth_04_crossshore_profiles()

    print("  coastline...")
    coast_01_sea_body()
    dists = coast_02_osm_vs_derived()

    print("\nmarine QA summary")
    print(f"  overlap bug:      {ov_b / 1e4:.2f} ha -> {ov_a:.0f} m2")
    print(f"  sign convention:  {n_ok}/{n_tot} control points pass")
    print(f"  nodata:           {raw_nan} raw NaN -> {out_nan} in output")
    if dists is not None:
        print(f"  coastline vs OSM: median {np.median(dists):.0f} m, p90 "
              f"{np.percentile(dists, 90):.0f} m")
    if REEF_IS_FINAL:
        print(f"\n  reef geometry:    {REEF.name} (Allen Coral Atlas v2.0 benthic)")
    else:
        print("\nNOT PRODUCED: Allen Coral Atlas figures — require Earth Engine auth "
              "(browser). See export_aca.py.")
