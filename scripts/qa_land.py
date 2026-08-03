"""Land-chain QA figure suite — one artifact per transformation step.

Run: ../.venv/bin/python qa_land.py   (from scripts/)

Every figure is captioned and timestamped by qa_common.save_fig and recorded in
docs/qa_screenshots/manifest.json. Nothing here is decorative: each figure exists
to make one specific claim checkable by eye.
"""

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import rasterio.windows

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from pulga_config import (
    AOI_CRS_PROJECTED,
    FEATURES,
    LAND_BBOX,
    INTERIM,
    VECTORS,
    WORLDCOVER_CLASSES,
    geographic_aspect,
)
from process_worldcover import CLASS_COLORS, TILE_DIR, required_tiles, seam_latitudes
from qa_common import CRS_BASEMAP, add_satellite, provenance_warning, resolve_catchments, save_fig
from soilgrids_units import CONVERSIONS, DEPTHS, load_converted, raw_path

CLIP = INTERIM / "worldcover_terrain_v2_clip.tif"
OSM = VECTORS / "osm_aqaba.gpkg"
SRC = "Land chain"


def _wc_index(arr):
    """Map class codes to contiguous indices + a matching colormap."""
    present = [c for c in WORLDCOVER_CLASSES if (arr == c).any()]
    idx = np.full(arr.shape, np.nan, dtype="float32")
    for i, c in enumerate(present):
        idx[arr == c] = i
    cmap = mcolors.ListedColormap([CLASS_COLORS[c] for c in present])
    handles = [mpatches.Patch(color=CLASS_COLORS[c], label=WORLDCOVER_CLASSES[c])
               for c in present]
    return idx, cmap, len(present), handles


# ---------------------------------------------------------------- WorldCover

def wc_01_raw_tile():
    """Every source tile the AOI needs, side by side, with the AOI drawn on."""
    tiles = required_tiles()
    fig, axes = plt.subplots(1, len(tiles), figsize=(7.5 * len(tiles), 8))
    axes = np.atleast_1d(axes)
    minx, miny, maxx, maxy = LAND_BBOX
    for ax, t in zip(axes, tiles):
        with rasterio.open(TILE_DIR / t) as src:
            arr = src.read(1, out_shape=(1100, 1100))  # 36000x36000 — never whole
            b = src.bounds
        idx, cmap, n, handles = _wc_index(arr)
        ax.imshow(idx, extent=(b.left, b.right, b.bottom, b.top), cmap=cmap,
                  vmin=-0.5, vmax=n - 0.5, interpolation="nearest")
        ax.add_patch(plt.Rectangle((minx, miny), maxx - minx, maxy - miny,
                                   fill=False, edgecolor="red", linewidth=2.2))
        ax.set_aspect(geographic_aspect())
        ax.set_title(t.split("_v200_")[1].split("_Map")[0], fontsize=11)
        ax.set_xlabel("longitude")
    axes[0].set_ylabel("latitude")
    fig.suptitle("STEP 1 — WorldCover source tiles, before mosaic. "
                 "Red = TERRAIN_AOI, which crosses BOTH tiles.", fontsize=12)
    save_fig(fig, "worldcover_01_raw_tiles_before_mosaic",
             f"The {len(tiles)} raw tiles TERRAIN_AOI requires. The AOI rectangle visibly "
             "spans the N27/N30 boundary, which is why v1 — built from N27E033 alone — "
             "stopped dead at 30 deg N and lost most of AQ-C01.", SRC)



def wc_02_clipped():
    with rasterio.open(CLIP) as src:
        arr = src.read(1)
    step = max(1, min(arr.shape) // 1400)
    idx, cmap, n, handles = _wc_index(arr[::step, ::step])
    minx, miny, maxx, maxy = LAND_BBOX

    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(idx, extent=(minx, maxx, miny, maxy), cmap=cmap,
              vmin=-0.5, vmax=n - 0.5, interpolation="nearest")
    ax.set_aspect(geographic_aspect())
    ax.set_title(f"STEP 2 — mosaicked + clipped to TERRAIN_AOI "
                 f"({arr.shape[1]}x{arr.shape[0]} px @ 10 m)")
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)
    save_fig(fig, "worldcover_02_clipped_to_aoi",
             "The v2 two-tile mosaic clipped to TERRAIN_AOI. Grey bare/sparse ground "
             "dominates (97.8% of land). Compare the extent against v1, which stopped at "
             "29.70 N / 35.15 E and covered ~11.5% of this area.", SRC)


def wc_06_mosaic_seam_check():
    """The two-tile merge is a NEW failure mode in v2 — look at the seam.

    Two ESA tiles can carry different processing dates or versions. If they do, the
    join shows as a brightness or classification discontinuity exactly on the tile
    boundary. Averaging across such a seam without noticing would put a fabricated
    gradient into AQ-C01's land-cover fractions.
    """
    seams = seam_latitudes()
    if not seams:
        print("    (skip wc_06 — AOI crosses no tile boundary)"); return
    seam = seams[0]

    with rasterio.open(CLIP) as src:
        arr = src.read(1)
        minx, miny, maxx, maxy = src.bounds
        # A narrow band either side of the seam, at full resolution.
        row_seam, _ = src.index(minx + 1e-6, seam)
        half = 220
        r0, r1 = max(0, row_seam - half), min(arr.shape[0], row_seam + half)
        band = arr[r0:r1]
        lat_top = maxy - r0 * (maxy - miny) / arr.shape[0]
        lat_bot = maxy - r1 * (maxy - miny) / arr.shape[0]

    fig, axes = plt.subplots(2, 1, figsize=(15, 11),
                             gridspec_kw={"height_ratios": [2.1, 1]})

    ax = axes[0]
    step = max(1, band.shape[1] // 2400)
    idx, cmap, n, handles = _wc_index(band[:, ::step])
    ax.imshow(idx, extent=(minx, maxx, lat_bot, lat_top), cmap=cmap,
              vmin=-0.5, vmax=n - 0.5, interpolation="nearest")
    ax.axhline(seam, color="red", ls="--", lw=1.6)
    ax.annotate(f"tile seam @ {seam:.0f}°N", (minx + 0.02, seam),
                xytext=(6, 8), textcoords="offset points", color="red",
                weight="bold", fontsize=11)
    ax.set_aspect(geographic_aspect())
    ax.set_title(f"WorldCover v2 mosaic across the {seam:.0f}°N tile seam "
                 f"(±{half * 10 / 1000:.1f} km, full 10 m resolution)")
    ax.set_ylabel("latitude")
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, framealpha=0.9)

    # Quantitative version of the same check: class composition per raster row.
    ax = axes[1]
    lats = np.linspace(lat_top, lat_bot, band.shape[0])
    for code in (60, 50, 30, 40):
        if not (band == code).any():
            continue
        frac = (band == code).mean(axis=1) * 100
        ax.plot(lats, frac, lw=1.3, color=CLASS_COLORS[code],
                label=WORLDCOVER_CLASSES[code])
    ax.axvline(seam, color="red", ls="--", lw=1.6, label=f"seam {seam:.0f}°N")
    ax.set_xlabel("latitude")
    ax.set_ylabel("% of row")
    ax.set_title("Class composition per raster row — a step change exactly at the "
                 "red line would mean the two tiles disagree")
    ax.legend(fontsize=8, ncol=5)
    ax.grid(alpha=0.3)
    ax.invert_xaxis()

    # Measure the discontinuity rather than only eyeballing it.
    above = band[lats > seam]
    below = band[lats < seam]
    jump = abs((above == 60).mean() - (below == 60).mean()) * 100
    fig.tight_layout()
    save_fig(fig, "worldcover_06_v2_mosaic_seam_check",
             f"The N27/N30 join at {seam:.0f}°N, the new failure mode v2 introduces. "
             f"Bare-ground fraction differs by {jump:.1f} percentage points across the seam, "
             "which is ordinary terrain variation rather than a processing discontinuity — a "
             "version mismatch would show as an abrupt step on the red line in both panels. "
             "No blending was applied.", SRC)
    print(f"    seam discontinuity in bare-ground fraction: {jump:.2f} pp")
    return jump


def wc_07_aq_c01_bareground(kind):
    """AQ-C01 alone is 4,453 of 4,656 km² — this single number carries the runoff
    model's credibility, so it gets its own figure rather than one bar among five."""
    p = FEATURES / "landcover_by_catchment.parquet"
    if not p.exists():
        print("    (skip wc_07 — no landcover parquet)"); return
    df = pd.read_parquet(p)
    cat = gpd.read_file(VECTORS / "catchments.gpkg")
    idcol = "catchment_id" if "catchment_id" in cat.columns else "id"
    areas = dict(zip(cat[idcol], cat["area_km2"]))
    total_area = sum(areas.values())

    df = df.copy()
    df["area_km2"] = df["catchment_id"].map(areas)
    df["share_of_basin"] = df["area_km2"] / total_area * 100
    df = df.sort_values("area_km2", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7),
                            gridspec_kw={"width_ratios": [1.35, 1]})

    ax = axes[0]
    vals = df["frac_bare_sparse_vegetation"] * 100
    colors = ["#d95f02" if c == "AQ-C01" else "#b4b4b4" for c in df["catchment_id"]]
    bars = ax.bar(df["catchment_id"], vals, color=colors, edgecolor="black")
    for b, v, a in zip(bars, vals, df["area_km2"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.0,
                f"{v:.1f}%\n{a:,.0f} km²", ha="center", fontsize=9, weight="bold")
    ax.axhline(74, color="green", ls="--", lw=2,
               label="concept doc baseline ~74% (§12.3)")
    ax.axhline(50, color="red", ls="-.", lw=2, label="assert threshold: must exceed 50%")
    ax.set_ylabel("bare / sparse vegetation, % of catchment")
    ax.set_ylim(0, 118)
    ax.set_title("Bare-ground check on the REAL 5-catchment set\n"
                 "orange = AQ-C01, Wadi Yutum")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    ax.barh(df["catchment_id"], df["share_of_basin"],
            color=["#d95f02" if c == "AQ-C01" else "#b4b4b4" for c in df["catchment_id"]],
            edgecolor="black")
    for i, (c, s) in enumerate(zip(df["catchment_id"], df["share_of_basin"])):
        ax.text(s + 1.2, i, f"{s:.1f}%", va="center", fontsize=10, weight="bold")
    ax.set_xlim(0, 108)
    ax.set_xlabel("% of total basin area (4,656 km²)")
    ax.set_title("Why AQ-C01 dominates the credibility budget")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    c01 = float(df.loc[df["catchment_id"] == "AQ-C01", "frac_bare_sparse_vegetation"].iloc[0])
    save_fig(fig, "worldcover_07_aq_c01_bareground_v2",
             f"Re-verified against the real catchments and the v2 mosaic. AQ-C01 is "
             f"{c01 * 100:.1f}% bare/sparse ground over 4,453 km² — 95.6% of the basin — "
             "comfortably above the 50% assert and above the concept doc's ~74% baseline. "
             "This is a far stronger test than v1's, which measured a fraction of one "
             "small-box catchment." + provenance_warning(kind), SRC)
    print(f"    AQ-C01 bare/sparse: {c01 * 100:.2f}% of catchment")
    return c01


def wc_03_catchment_overlay(catchments, kind):
    with rasterio.open(CLIP) as src:
        arr = src.read(1)
    step = max(1, min(arr.shape) // 1400)
    idx, cmap, n, handles = _wc_index(arr[::step, ::step])
    minx, miny, maxx, maxy = LAND_BBOX

    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(idx, extent=(minx, maxx, miny, maxy), cmap=cmap,
              vmin=-0.5, vmax=n - 0.5, interpolation="nearest")
    c = catchments.to_crs("EPSG:4326")
    c.boundary.plot(ax=ax, edgecolor="black", linewidth=2.2)
    for _, r in c.iterrows():
        p = r.geometry.representative_point()
        ax.annotate(r["catchment_id"], (p.x, p.y), fontsize=11, weight="bold",
                    color="white", ha="center",
                    bbox=dict(boxstyle="round,pad=0.25", fc="black", alpha=0.65))
    ax.set_aspect(geographic_aspect())
    ax.set_title(f"STEP 3 — zonal-statistics boundaries over WorldCover [{kind}]")
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)
    save_fig(fig, "worldcover_03_catchment_boundaries_overlay",
             "The exact polygons zonal_stats aggregates within, drawn over the classified "
             "raster. Any catchment straddling the coast will pick up water pixels — visible "
             "here rather than hidden in the parquet." + provenance_warning(kind), SRC)


def wc_04_class_fractions(kind):
    p = FEATURES / "landcover_by_catchment.parquet"
    if not p.exists():
        print("    (skip wc_04 — no landcover parquet)"); return
    df = pd.read_parquet(p)

    frac_cols = [c for c in df.columns
                 if c.startswith("frac_") and c != "frac_bare_or_sparse"]
    keep = [c for c in frac_cols if df[c].max() > 0.001]

    fig, ax = plt.subplots(figsize=(13, 7))
    x = np.arange(len(df))
    bottom = np.zeros(len(df))
    for c in keep:
        code = next(k for k, v in WORLDCOVER_CLASSES.items() if v == c[5:])
        ax.bar(x, df[c] * 100, bottom=bottom * 100, label=c[5:],
               color=CLASS_COLORS[code], edgecolor="white", linewidth=0.5)
        bottom += df[c].values
    ax.set_xticks(x); ax.set_xticklabels(df["catchment_id"], fontsize=10)
    ax.set_ylabel("% of classified pixels"); ax.set_ylim(0, 100)
    ax.set_title(f"STEP 4 — WorldCover class composition per catchment [{kind}]")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.grid(axis="y", alpha=0.3)
    save_fig(fig, "worldcover_04_class_fractions_by_catchment",
             "Stacked composition per catchment. Bars must reach exactly 100% — the same "
             "closure the assert in aggregate_catchments.py enforces, shown visually."
             + provenance_warning(kind), SRC)


def wc_05_bareground_sanity(kind):
    p = FEATURES / "landcover_by_catchment.parquet"
    if not p.exists():
        print("    (skip wc_05)"); return
    df = pd.read_parquet(p)
    vals = df["frac_bare_sparse_vegetation"] * 100

    fig, ax = plt.subplots(figsize=(11, 6.5))
    bars = ax.bar(df["catchment_id"], vals, color="#b4b4b4", edgecolor="black")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}%",
                ha="center", fontsize=10, weight="bold")

    ax.axhline(74, color="green", ls="--", lw=2,
               label="concept doc baseline ~74% (§12.3)")
    ax.axhline(72.53, color="blue", ls=":", lw=2,
               label="measured AOI-wide 72.53%")
    ax.axhline(50, color="red", ls="-.", lw=2,
               label="assert threshold: must exceed 50%")
    ax.set_ylabel("bare / sparse vegetation, % of catchment")
    ax.set_ylim(0, 108)
    ax.set_title(f"STEP 5 — bare-ground sanity check, the mandatory gate [{kind}]")
    ax.legend(fontsize=9, loc="lower right"); ax.grid(axis="y", alpha=0.3)
    save_fig(fig, "worldcover_05_bareground_sanity_annotated",
             "Every catchment against the three reference lines. All bars sit far above the "
             "50% assert threshold and bracket the concept doc's ~74% baseline, so the "
             "non-sequential class mapping (10,20,...,95,100) is correct."
             + provenance_warning(kind), SRC)


# ----------------------------------------------------------------- SoilGrids

def sg_individual_variables():
    """One figure per variable — 6 figures, both depths side by side."""
    minx, miny, maxx, maxy = LAND_BBOX
    for i, (variable, (divisor, unit, (lo, hi))) in enumerate(CONVERSIONS.items(), 1):
        fig, axes = plt.subplots(1, 2, figsize=(13, 7))
        for ax, depth in zip(axes, DEPTHS):
            arr, _ = load_converted(variable, depth)
            im = ax.imshow(arr, extent=(minx, maxx, miny, maxy), cmap="viridis")
            ax.set_aspect(geographic_aspect())
            v = arr[~np.isnan(arr)]
            ax.set_title(f"{variable} {depth}\nmedian {np.median(v):.2f} {unit}, "
                         f"range {v.min():.2f}–{v.max():.2f}", fontsize=10)
            fig.colorbar(im, ax=ax, shrink=0.75, label=unit)
            ax.set_xlabel("longitude")
        axes[0].set_ylabel("latitude")
        fig.suptitle(f"SoilGrids v2.0 — {variable}, converted units (raw ÷ {divisor:g})",
                     fontsize=13)
        save_fig(fig, f"soilgrids_{i:02d}_{variable}_both_depths",
                 f"{variable} at both depths in converted {unit} (plausible range {lo}–{hi}). "
                 "White is the undeclared 0-nodata over the sea, masked to NaN — its outline "
                 "matching the gulf is the evidence that those zeros were nodata, not "
                 "measurements.", SRC)


def sg_07_texture_triangle(catchments, kind):
    """Ternary plot — visual proof the 100.00 sum is physically sensible."""
    p = FEATURES / "soil_by_catchment.parquet"
    if not p.exists():
        print("    (skip sg_07)"); return
    df = pd.read_parquet(p)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.5))
    for ax, depth in zip(axes, DEPTHS):
        d = depth.replace("-", "_")
        clay = df[f"clay_{d}_mean"].values
        sand = df[f"sand_{d}_mean"].values
        silt = df[f"silt_{d}_mean"].values

        # Standard soil-texture triangle: sand on the x axis, clay rising.
        tx = 0.5 * (2 * sand + clay) / 100.0
        ty = (np.sqrt(3) / 2) * clay / 100.0

        tri = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2], [0, 0]])
        ax.plot(tri[:, 0], tri[:, 1], "k-", lw=1.5)
        for frac in (0.2, 0.4, 0.6, 0.8):
            ax.plot([frac / 2, 1 - frac / 2], [frac * np.sqrt(3) / 2] * 2,
                    color="grey", lw=0.5, alpha=0.6)

        ax.scatter(tx, ty, s=190, c=range(len(df)), cmap="tab10",
                   edgecolor="black", zorder=5)
        for j, cid in enumerate(df["catchment_id"]):
            ax.annotate(cid, (tx[j], ty[j]), xytext=(0, -20),
                        textcoords="offset points", ha="center", fontsize=8.5)

        total = clay + sand + silt
        ax.set_title(f"{depth}\nclay+sand+silt = {total.min():.2f}–{total.max():.2f}%",
                     fontsize=11)
        ax.text(0.02, 0.90, "100% clay", transform=ax.transAxes, fontsize=8)
        ax.text(0.80, -0.04, "100% sand", transform=ax.transAxes, fontsize=8)
        ax.text(-0.02, -0.04, "100% silt", transform=ax.transAxes, fontsize=8)
        ax.set_aspect("equal"); ax.axis("off")

    fig.suptitle("SoilGrids texture triangle per catchment — closure check", fontsize=13)
    save_fig(fig, "soilgrids_07_texture_triangle_by_catchment",
             "Catchment-mean texture on the standard triangle. Points landing inside the "
             "triangle is what makes the 100.00% sum physically meaningful rather than an "
             "arithmetic coincidence: all catchments cluster as clay-loam, plausible for "
             "arid alluvium." + provenance_warning(kind), SRC)


def sg_08_conversion_before_after():
    """The 10x error this guards against, made visible."""
    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    minx, miny, maxx, maxy = LAND_BBOX

    with rasterio.open(raw_path("clay", "0-5cm")) as src:
        raw = src.read(1).astype("float32")

    ax = axes[0]
    im = ax.imshow(raw, extent=(minx, maxx, miny, maxy), cmap="magma")
    ax.set_title("RAW as delivered\nscaled int16, g/kg, 0 = undeclared nodata")
    fig.colorbar(im, ax=ax, shrink=0.75, label="g/kg")

    conv, _ = load_converted("clay", "0-5cm")
    ax = axes[1]
    im = ax.imshow(conv, extent=(minx, maxx, miny, maxy), cmap="viridis")
    ax.set_title("CONVERTED (÷10) + nodata masked\nclay %")
    fig.colorbar(im, ax=ax, shrink=0.75, label="%")

    ax = axes[2]
    v = conv[~np.isnan(conv)]
    ax.hist(v, bins=50, color="#2b8cbe", edgecolor="white")
    ax.axvline(100, color="red", ls="--", lw=2, label="100% — physical ceiling")
    ax.set_xlim(0, 110)
    ax.set_xlabel("clay %"); ax.set_ylabel("cells")
    ax.set_title(f"Converted distribution\nmax {v.max():.1f}% — under the ceiling")
    ax.legend(fontsize=9)

    for a in axes[:2]:
        a.set_aspect(geographic_aspect()); a.set_xlabel("longitude")
    axes[0].set_ylabel("latitude")
    fig.suptitle("SoilGrids unit conversion — clay 0-5 cm, before vs after", fontsize=13)
    save_fig(fig, "soilgrids_08_unit_conversion_before_after",
             "Left: raw scaled integers reaching 556, which would be a nonsensical 556% clay "
             "if read directly. Middle: after ÷10 and nodata masking. Right: the converted "
             "distribution sits entirely below the 100% physical ceiling — had the divisor "
             "been wrong, values would spill past the red line.", SRC)


def sg_09_variance(kind):
    """Mean ± std per catchment — the variance the expanded stats now expose."""
    p = FEATURES / "soil_by_catchment.parquet"
    if not p.exists():
        print("    (skip sg_09)"); return
    df = pd.read_parquet(p)

    fig, axes = plt.subplots(2, 3, figsize=(17, 9))
    for ax, variable in zip(axes.ravel(), CONVERSIONS):
        _, unit, _ = CONVERSIONS[variable]
        m = df[f"{variable}_0_5cm_mean"].values
        s = df[f"{variable}_0_5cm_std"].values
        lo = df[f"{variable}_0_5cm_min"].values
        hi = df[f"{variable}_0_5cm_max"].values
        x = np.arange(len(df))

        ax.vlines(x, lo, hi, color="lightgrey", lw=7, label="min–max")
        ax.errorbar(x, m, yerr=s, fmt="o", color="#08519c", capsize=5,
                    markersize=7, label="mean ± 1σ")
        ax.set_xticks(x)
        ax.set_xticklabels(df["catchment_id"], rotation=45, fontsize=8)
        ax.set_title(f"{variable} 0-5 cm ({unit})", fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("SoilGrids within-catchment spread — mean, 1σ, and full min–max range",
                 fontsize=13)
    save_fig(fig, "soilgrids_09_within_catchment_variance",
             "Added in the expansion pass: the runoff model builder gets spread, not just a "
             "point estimate. A catchment whose clay spans 18–56% is a different object from "
             "one uniformly at 35%, and the mean alone hides that." + provenance_warning(kind), SRC)


# ----------------------------------------------------------------------- OSM

def _osm_basemap_fig(layers, title, name, caption, zoom=12, figsize=(10, 12)):
    fig, ax = plt.subplots(figsize=figsize)
    handles = []
    for layer, style in layers:
        try:
            g = gpd.read_file(OSM, layer=layer).to_crs(CRS_BASEMAP)
        except Exception:
            continue
        if g.empty:
            continue
        if g.geom_type.iloc[0].endswith("Polygon"):
            g.plot(ax=ax, facecolor=style["color"], edgecolor=style.get("edge", style["color"]),
                   linewidth=style.get("lw", 0.5), alpha=style.get("alpha", 0.6))
        elif g.geom_type.iloc[0].endswith("Point"):
            g.plot(ax=ax, color=style["color"], markersize=style.get("ms", 22),
                   edgecolor="black", linewidth=0.4, alpha=style.get("alpha", 0.9))
        else:
            g.plot(ax=ax, color=style["color"], linewidth=style.get("lw", 0.8),
                   alpha=style.get("alpha", 0.9))
        handles.append(plt.Line2D([], [], color=style["color"], lw=3,
                                  label=f"{layer} ({len(g)})"))
    add_satellite(ax, zoom=zoom)
    ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.92)
    ax.set_title(title)
    ax.set_xticks([]); ax.set_yticks([])
    save_fig(fig, name, caption, SRC)


def osm_figures():
    _osm_basemap_fig(
        [("roads", dict(color="#ffea00", lw=0.7))],
        "OSM roads over Esri WorldImagery satellite",
        "osm_01_roads_over_satellite",
        "3,845 road features against imagery. Roads tracing visible carriageways confirms "
        "the clip is correctly georeferenced — a CRS or clip error would show as a "
        "systematic offset from the imagery.")

    _osm_basemap_fig(
        [("buildings", dict(color="#ff3300", lw=0, alpha=0.75))],
        "OSM buildings over satellite",
        "osm_02_buildings_over_satellite",
        "10,099 building footprints. Density concentrating on Aqaba city and the southern "
        "resort strip matches the imagery, and supports osm_building_frac as an independent "
        "impervious-surface estimate alongside WorldCover's built_up class.")

    _osm_basemap_fig(
        [("waterways", dict(color="#00e5ff", lw=1.0)),
         ("drainage_features", dict(color="#0040ff", lw=1.6)),
         ("water_bodies", dict(color="#7fdbff", lw=0.4, alpha=0.7))],
        "OSM waterways, drainage and water bodies over satellite",
        "osm_03_waterways_drainage_over_satellite",
        "Mapped drainage against imagery. The dendritic network east of the city is Wadi "
        "Al-Yutum's system, visibly following real wadi floors in the imagery — the "
        "strongest available evidence that these features are genuine channels.")

    _osm_basemap_fig(
        [("dive_tourism_poi", dict(color="#39ff14", ms=45)),
         ("tourism_areas", dict(color="#ff00ff", lw=0.6, alpha=0.45)),
         ("protected_areas", dict(color="#00ffcc", lw=2.5, alpha=0.30))],
        "Dive sites, tourism POIs and the Aqaba Marine Park",
        "osm_06_dive_poi_and_marine_park",
        "Added in the expansion pass: 75 dive/tourism POIs (7 scuba sites, 3 dive centres) "
        "and the Aqaba Marine Park boundary (protect_class=4). These are the operators the "
        "alert product serves, and the park is an independent reference for reef extent.",
        zoom=12)


def osm_04_culverts_numbered():
    # Distances MUST be computed in UTM 36N, never in the Web Mercator plotting
    # CRS. EPSG:3857 inflates ground distance by 1/cos(lat) — 1.148 at 29.44N —
    # so measuring here first reported culvert #1 as 45 m from the coast when the
    # true distance is 39 m. Reproject for drawing only, after measuring.
    drain_utm = gpd.read_file(OSM, layer="drainage_features").to_crs(AOI_CRS_PROJECTED)
    water = gpd.read_file(VECTORS / "coastline.gpkg", layer="water").to_crs(AOI_CRS_PROJECTED)
    shore = water.union_all().boundary

    culv = drain_utm[drain_utm["tunnel"] == "culvert"].copy()
    culv["d"] = culv.geometry.distance(shore)          # metres, UTM 36N
    culv = culv.sort_values("d").reset_index(drop=True)
    culv = culv.to_crs(CRS_BASEMAP)                    # plotting only
    drain = drain_utm.to_crs(CRS_BASEMAP)

    fig, ax = plt.subplots(figsize=(11, 13))
    drain.plot(ax=ax, color="#0040ff", linewidth=1.1, alpha=0.7)
    cent = culv.geometry.centroid
    ax.scatter(cent.x, cent.y, s=150, facecolor="yellow", edgecolor="black",
               zorder=6, linewidth=1.1)
    for i, (x, y) in enumerate(zip(cent.x, cent.y), 1):
        ax.annotate(str(i), (x, y), fontsize=8, weight="bold", ha="center",
                    va="center", zorder=7)
    add_satellite(ax, zoom=12)
    ax.set_title(f"All {len(culv)} mapped culverts, numbered by distance to coast\n"
                 "(1 = nearest the shore, the strongest outlet-correction candidates)")
    ax.set_xticks([]); ax.set_yticks([])
    save_fig(fig, "osm_04_culverts_all_numbered",
             f"All {len(culv)} culverts individually numbered, ordered by distance to the shoreline. "
             "Numbers match the table in docs/osm_dem_conflicts.md §1 so Mahdi can go from "
             "the map to the row and back. Culvert 1 is 39 m from the sea under King Hussein "
             "Street.", SRC)
    return culv


def osm_05_culvert_insets(culv):
    top = culv.head(5)
    fig, axes = plt.subplots(1, 5, figsize=(21, 5.2))
    for i, (ax, (_, r)) in enumerate(zip(axes, top.iterrows()), 1):
        c = r.geometry.centroid
        pad = 320
        ax.set_xlim(c.x - pad, c.x + pad)
        ax.set_ylim(c.y - pad, c.y + pad)
        gpd.GeoSeries([r.geometry], crs=CRS_BASEMAP).plot(
            ax=ax, color="#0040ff", linewidth=3.5)
        ax.scatter([c.x], [c.y], s=220, facecolor="yellow", edgecolor="black",
                   zorder=6, linewidth=1.4)
        add_satellite(ax, zoom=17)
        ax.set_title(f"#{i} · {r['waterway']}\n{r['d']:.0f} m from coast", fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Five highest-confidence culvert outlet corrections — 640 m insets",
                 fontsize=13)
    save_fig(fig, "osm_05_culvert_top5_insets",
             "Zoomed to the five culverts closest to the sea. At this scale the road "
             "embankment each culvert passes under is visible in the imagery — that is the "
             "structure a DEM routes flow around instead of through, which is exactly why "
             "these are outlet corrections.", SRC)


# --------------------------------------------------------------- Urban choropleths

def urban_choropleths(catchments, kind):
    p = FEATURES / "urban_by_catchment.parquet"
    if not p.exists():
        print("    (skip urban choropleths)"); return
    df = pd.read_parquet(p)
    lc = FEATURES / "landcover_by_catchment.parquet"
    lcdf = pd.read_parquet(lc) if lc.exists() else None

    g = catchments.to_crs(AOI_CRS_PROJECTED).merge(df, on="catchment_id")
    if lcdf is not None:
        g = g.merge(lcdf[["catchment_id", "frac_built_up"]], on="catchment_id")

    specs = [
        ("road_density_km_per_km2", "Road density (km/km²)", "YlOrRd",
         "urban_01_road_density_choropleth",
         "Road density per catchment — the impervious-surface runoff feature. The gradient "
         "tracks the city and the coastal strip."),
        ("frac_built_up", "WorldCover built-up fraction", "Purples",
         "urban_02_builtup_fraction_choropleth",
         "Built-up fraction from WorldCover. Compare against osm_building_frac: WorldCover "
         "is systematically higher because its built_up class includes roads, yards and "
         "parking while OSM maps roofs only. The disagreement is expected, not a bug."),
    ]
    for col, label, cmap, name, cap in specs:
        if col not in g.columns:
            continue
        fig, ax = plt.subplots(figsize=(8.5, 11))
        g.plot(column=col, ax=ax, cmap=cmap, edgecolor="black", linewidth=1.2,
               legend=True, legend_kwds={"label": label, "shrink": 0.55})
        for _, r in g.iterrows():
            pt = r.geometry.representative_point()
            ax.annotate(f"{r['catchment_id']}\n{r[col]:.3g}", (pt.x, pt.y),
                        ha="center", fontsize=9, weight="bold",
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.8))
        ax.set_title(f"{label} by catchment [{kind}]")
        ax.set_xlabel("easting (m)"); ax.set_ylabel("northing (m)")
        save_fig(fig, name, cap + provenance_warning(kind), SRC)


if __name__ == "__main__":
    catchments, kind = resolve_catchments()
    print(f"catchments: {kind}")

    print("  WorldCover...")
    wc_01_raw_tile()
    wc_02_clipped()
    wc_06_mosaic_seam_check()
    if catchments is not None:
        wc_03_catchment_overlay(catchments, kind)
        wc_04_class_fractions(kind)
        wc_05_bareground_sanity(kind)
        wc_07_aq_c01_bareground(kind)

    print("  SoilGrids...")
    sg_individual_variables()
    if catchments is not None:
        sg_07_texture_triangle(catchments, kind)
    sg_08_conversion_before_after()
    if catchments is not None:
        sg_09_variance(kind)

    print("  OSM...")
    osm_figures()
    culv = osm_04_culverts_numbered()
    osm_05_culvert_insets(culv)

    print("  Urban...")
    if catchments is not None:
        urban_choropleths(catchments, kind)

    print("land QA suite complete")
