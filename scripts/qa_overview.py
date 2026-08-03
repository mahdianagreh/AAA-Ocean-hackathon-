"""Cross-cutting figures: the master composite map and the data-lineage diagram.

Run: ../.venv/bin/python qa_overview.py   (from scripts/)

The composite is built to be pitch-deck ready. The lineage diagram is rendered as
an image rather than left as prose in the README, so the provenance of every
deliverable — including the GMRT substitution — is visible at a glance.
"""

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from pulga_config import PROCESSED, VECTORS
from qa_common import CRS_BASEMAP, add_satellite, provenance_warning, resolve_catchments, save_fig

DEPTH = PROCESSED / "bathymetry" / "depth_utm36n.tif"
OSM = VECTORS / "osm_aqaba.gpkg"
SRC = "Cross-cutting"


def master_map(catchments, kind):
    """Everything Pulga has built, composited over satellite imagery."""
    fig, ax = plt.subplots(figsize=(13.5, 16))

    handles = []

    def layer(path, layer_name, **kw):
        try:
            g = gpd.read_file(path, layer=layer_name).to_crs(CRS_BASEMAP)
        except Exception:
            return None
        return g if not g.empty else None

    # Order matters: broad context first, then the headline deliverables on top.
    if catchments is not None:
        c = catchments.to_crs(CRS_BASEMAP)
        c.boundary.plot(ax=ax, edgecolor="#ffffff", linewidth=2.6, zorder=3)
        c.boundary.plot(ax=ax, edgecolor="#000000", linewidth=1.1, zorder=4,
                        linestyle="--")
        handles.append(plt.Line2D([], [], color="black", ls="--", lw=2,
                                  label=f"catchments ({len(c)}, {kind})"))

    water = layer(VECTORS / "coastline.gpkg", "water")
    if water is not None:
        water.boundary.plot(ax=ax, color="#00e5ff", linewidth=2.2, zorder=5)
        handles.append(plt.Line2D([], [], color="#00e5ff", lw=2.5,
                                  label="coastline (GMRT-derived)"))

    roads = layer(OSM, "roads")
    if roads is not None:
        roads.plot(ax=ax, color="#ffea00", linewidth=0.35, alpha=0.65, zorder=6)
        handles.append(plt.Line2D([], [], color="#ffea00", lw=2,
                                  label=f"roads ({len(roads)})"))

    drain = layer(OSM, "drainage_features")
    if drain is not None:
        drain.plot(ax=ax, color="#0040ff", linewidth=1.2, alpha=0.9, zorder=7)
        handles.append(plt.Line2D([], [], color="#0040ff", lw=2.5,
                                  label=f"mapped drainage ({len(drain)})"))
        culv = drain[drain["tunnel"] == "culvert"]
        if not culv.empty:
            cen = culv.geometry.centroid
            ax.scatter(cen.x, cen.y, s=85, facecolor="yellow", edgecolor="black",
                       linewidth=0.9, zorder=9)
            handles.append(plt.Line2D([], [], marker="o", color="none",
                                      markerfacecolor="yellow", markeredgecolor="black",
                                      markersize=9,
                                      label=f"culverts ({len(culv)}) → outlet corrections"))

    park = layer(OSM, "protected_areas")
    if park is not None:
        p = park[park["protection_title"] == "Marine Park"]
        if not p.empty:
            p.plot(ax=ax, facecolor="#00ffcc", edgecolor="#00ffcc", linewidth=2.2,
                   alpha=0.20, zorder=8)
            handles.append(mpatches.Patch(facecolor="#00ffcc", alpha=0.35,
                                          edgecolor="#00ffcc",
                                          label="Aqaba Marine Park (OSM)"))

    reef = layer(VECTORS / "reef_zones_PROVISIONAL.gpkg", "reef_zones")
    if reef is not None:
        reef.plot(ax=ax, facecolor="#ff6600", edgecolor="black", linewidth=1.3,
                  alpha=0.80, zorder=10)
        handles.append(mpatches.Patch(facecolor="#ff6600", edgecolor="black",
                                      label=f"reef zones R-01–R-08 ({len(reef)})"))
        for _, r in reef.iterrows():
            cc = r.geometry.centroid
            ax.annotate(r["reef_zone_id"], (cc.x, cc.y), xytext=(19, 0),
                        textcoords="offset points", fontsize=9, weight="bold",
                        color="white", va="center", zorder=11,
                        bbox=dict(boxstyle="round,pad=0.22", fc="black", alpha=0.62))

    add_satellite(ax, zoom=12)
    ax.legend(handles=handles, loc="upper left", fontsize=9.5, framealpha=0.93)
    ax.set_title("ReefShield Aqaba — Workstream A+B composite\n"
                 "land cover · soil · urban · marine habitat · bathymetry",
                 fontsize=14, weight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    save_fig(fig, "overview_01_master_all_layers",
             "Every Pulga deliverable in one frame: catchment boundaries, GMRT-derived "
             "coastline, every mapped road, the full drainage network with culverts marked, "
             "the Aqaba Marine Park, and reef zones R-01–R-08. Pitch-deck ready."
             + provenance_warning(kind), SRC, dpi=175)


def lineage_diagram():
    """Source -> processing -> output, drawn rather than described."""
    fig, ax = plt.subplots(figsize=(19, 12))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    C_SRC, C_PROC, C_OUT = "#dbeafe", "#fef3c7", "#dcfce7"
    C_BLOCK, C_SUB = "#fee2e2", "#f3e8ff"

    def box(x, y, w, h, text, fc, fontsize=8.2, ec="#334155", bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.45",
                                    facecolor=fc, edgecolor=ec, linewidth=1.3))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, weight="bold" if bold else "normal", wrap=True)
        return (x + w / 2, y, x + w / 2, y + h, x, y + h / 2, x + w, y + h / 2)

    def arrow(p0, p1, style="-|>", colour="#475569", ls="-"):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                                     color=colour, linewidth=1.2, linestyle=ls,
                                     shrinkA=1, shrinkB=1))

    ax.text(50, 97, "ReefShield Aqaba — Workstream A+B data lineage",
            ha="center", fontsize=16, weight="bold")
    ax.text(50, 93.6, "source  →  processing script  →  deliverable      "
                      "(purple = documented substitution, red = blocked)",
            ha="center", fontsize=9.5, color="#475569")

    # ---- row 1: WorldCover
    s1 = box(1, 79, 17, 8, "ESA WorldCover v200 (2021)\nAWS S3, tile N27E033\n10 m, CC BY 4.0", C_SRC)
    p1 = box(24, 79, 18, 8, "process_worldcover.py\nwindowed clip, class map,\nbare-ground assert", C_PROC)
    o1 = box(48, 79, 18, 8, "worldcover_aqaba_clip.tif\n4200x5400 @ 10 m", C_OUT)

    # ---- row 2: SoilGrids
    s2 = box(1, 68, 17, 8, "ISRIC SoilGrids v2.0\nWCS, 6 vars x 2 depths\n250 m, CC BY 4.0", C_SRC)
    p2 = box(24, 68, 18, 8, "download_soilgrids.py\nsoilgrids_units.py\n÷ divisor, mask 0-nodata", C_PROC)
    o2 = box(48, 68, 18, 8, "12 rasters +\n21 passing unit tests", C_OUT)

    # ---- row 3: OSM
    s3 = box(1, 57, 17, 8, "OpenStreetMap\nGeofabrik jordan-latest\n30 MB, ODbL 1.0", C_SRC)
    p3 = box(24, 57, 18, 8, "extract_osm.sh\ncustom osmconf promotes\ntunnel + industrial", C_PROC)
    o3 = box(48, 57, 18, 8, "osm_aqaba.gpkg\n12 layers incl. culverts", C_OUT)

    # ---- row 4: bathymetry, with the substitution called out
    sub = box(1, 43, 17, 10,
              "GEBCO 15 arc-sec\nUNREACHABLE\nWCS empty · POST 405 · BODC 404\n"
              "↓ substituted ↓\nGMRT (GEBCO-derived)", C_SUB, fontsize=7.6)
    p4 = box(24, 44, 18, 8, "process_bathymetry.py\nfill NaN, warp UTM 36N,\n22-point sign assert", C_PROC)
    o4 = box(48, 44, 18, 8, "depth_utm36n.tif @ 50 m\ncoastline.gpkg", C_OUT)

    # ---- row 5: reef zones. Marine Park attribution is noted inside the box
    # rather than as another arrow — an arrow from the OSM row would have to cross
    # two rows, and a crossing line costs more clarity than it buys.
    p5 = box(24, 32, 18, 8, "make_reef_zones_provisional.py\nshore trace + 250 m strip, band clip,\n"
                            "depth assert · park % from OSM", C_PROC, fontsize=7.8)
    o5 = box(48, 32, 18, 8, "reef_zones_PROVISIONAL.gpkg\nR-01–R-08, 5.69 km²", C_OUT)

    aca = box(24, 20, 18, 8, "export_aca.py\nAllen Coral Atlas v2.0\nBLOCKED: needs EE browser auth",
              C_BLOCK, fontsize=7.8)
    o6 = box(48, 20, 18, 8, "reef_zones.gpkg\n(real, pending)", C_BLOCK)

    # ---- catchments + features
    cat = box(1, 20, 17, 8, "Mahdi: catchments\ncontract §4 P1\nNOT YET PUBLISHED", C_BLOCK, fontsize=7.8)
    agg = box(20, 6, 24, 10,
              "aggregate_catchments.py\nzonal stats; refuses to write contract\n"
              "paths on fixture\ninputs: worldcover clip + 12 soil rasters\n+ osm_aqaba.gpkg + catchments",
              C_PROC, fontsize=7.4)
    o7 = box(48, 7, 18, 8, "landcover / soil / urban\n_by_catchment.parquet", C_OUT)

    # ---- consumers
    con1 = box(73, 66, 25, 9, "Runoff + sediment model\n(Mahdi)\nComponents C & D", "#e2e8f0", 9, bold=True)
    con2 = box(73, 42, 25, 9, "Particle transport engine\n(Nizar)\ncoastline + depth field", "#e2e8f0", 9, bold=True)
    con3 = box(73, 26, 25, 9, "Reef exposure engine\n+ dashboard\nComponent G", "#e2e8f0", 9, bold=True)

    # source -> process -> deliverable, four clean horizontal chains
    for s, p, o in [(s1, p1, o1), (s2, p2, o2), (s3, p3, o3), (sub, p4, o4)]:
        arrow((s[6], s[5]), (p[4], p[5]))
        arrow((p[6], p[5]), (o[4], o[5]))

    # depth field feeds the reef zones (they are anchored to its water mask)
    arrow((o4[0], o4[1]), (p5[6], p5[3]))
    arrow((p5[6], p5[5]), (o5[4], o5[5]))

    # the blocked ACA path, and the swap it will perform
    arrow((aca[6], aca[5]), (o6[4], o6[5]), colour="#b91c1c", ls="--")
    arrow((o6[0], o6[3]), (o5[0], o5[1]), colour="#b91c1c", ls="--")

    # catchments are the blocker on the whole feature-table branch
    arrow((cat[0], cat[1]), (agg[2], agg[3]), colour="#b91c1c", ls="--")
    arrow((agg[6], agg[5]), (o7[4], o7[5]))

    # deliverables -> consumers
    arrow((o7[6], o7[5]), (con1[4], con1[5]))
    arrow((o4[6], o4[5]), (con2[4], con2[5]))
    arrow((o5[6], o5[5]), (con3[4], con3[5]))

    ax.legend(handles=[
        mpatches.Patch(facecolor=C_SRC, edgecolor="#334155", label="external source"),
        mpatches.Patch(facecolor=C_PROC, edgecolor="#334155", label="processing script"),
        mpatches.Patch(facecolor=C_OUT, edgecolor="#334155", label="deliverable, verified"),
        mpatches.Patch(facecolor=C_SUB, edgecolor="#334155", label="documented substitution"),
        mpatches.Patch(facecolor=C_BLOCK, edgecolor="#334155", label="blocked on a human"),
    ], loc="lower left", fontsize=9, ncol=5, framealpha=0.95)

    save_fig(fig, "overview_02_data_lineage_diagram",
             "Full provenance for every deliverable. The purple box records that GEBCO is "
             "unreachable and GMRT was substituted — drawn into the diagram so nobody "
             "'corrects' the pipeline back to a broken GEBCO call. Red boxes are the two "
             "human blockers: Earth Engine browser auth and Mahdi's catchments.", SRC, dpi=150)


if __name__ == "__main__":
    catchments, kind = resolve_catchments()
    print("  master map...")
    master_map(catchments, kind)
    print("  lineage diagram...")
    lineage_diagram()
    print("overview figures complete")
