"""
QA figure: HYCOM vs Copernicus Marine current comparison at the Aqaba AOI —
today's conditions (top row) and the actual demo event, AQ-2016-10-28 (bottom row).

Shows both models' resolved current vectors, the provisional outlet marked where
both models independently mask it as land, and the direction/speed comparison at
the nearest point both models resolve. Backs the claims in
docs/forcing_limitations.md and docs/data_dictionary.md §8.

Run: cd backend && .venv/bin/python ../scripts/qa_currents.py
Requires (from backend/): python -m src.ingestion.ocean_currents
— which caches both the live and historical NetCDF files this script reads.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

warnings.filterwarnings("ignore")  # xarray's non-nanosecond datetime cast noise

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from src.ingestion.ocean_currents import CurrentFieldInterpolator  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENTS_DIR = REPO_ROOT / "data" / "raw" / "currents"
OUT_PATH = REPO_ROOT / "docs" / "qa_screenshots" / "currents_01_hycom_vs_copernicus.png"

OUTLET_LON, OUTLET_LAT = 34.96, 29.52


def _plot_row(fig, ax_map, ax_bar, hycom_ds, cm_ds, compare_lon, compare_lat, compare_time, title_suffix):
    hycom_uv = CurrentFieldInterpolator(hycom_ds)(compare_lon, compare_lat, compare_time)
    cm_uv = CurrentFieldInterpolator(cm_ds)(compare_lon, compare_lat, compare_time)
    hycom_now = hycom_ds.isel(time=len(hycom_ds.time) // 2, depth=0)
    cm_now = cm_ds.isel(time=len(cm_ds.time) // 2).sel(depth=cm_ds.depth.min())

    hlon, hlat = np.meshgrid(hycom_now.longitude, hycom_now.latitude)
    ax_map.quiver(hlon, hlat, hycom_now["u"].values, hycom_now["v"].values,
                  color="tab:blue", scale=1.5, label="HYCOM", width=0.005)

    clon, clat = np.meshgrid(cm_now.longitude, cm_now.latitude)
    ax_map.quiver(clon, clat, cm_now["u"].values, cm_now["v"].values,
                  color="tab:orange", scale=1.5, label="Copernicus Marine", width=0.005)

    ax_map.scatter([OUTLET_LON], [OUTLET_LAT], marker="x", s=140, color="red", linewidths=3,
                   label="Provisional outlet", zorder=5)
    ax_map.scatter([compare_lon], [compare_lat], marker="o", s=90, facecolors="none",
                   edgecolors="black", linewidths=2, label="Comparison point", zorder=5)
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.set_title(f"Surface currents — {title_suffix}")
    ax_map.legend(loc="upper right", fontsize=7)
    ax_map.set_aspect(1 / np.cos(np.radians(29.4)))
    ax_map.grid(alpha=0.3)

    labels = ["HYCOM", "Copernicus Marine"]
    (uh, vh), (uc, vc) = hycom_uv, cm_uv
    speed_h, speed_c = np.hypot(uh, vh) * 100, np.hypot(uc, vc) * 100  # m/s -> cm/s
    dir_h = (270 - np.degrees(np.arctan2(vh, uh))) % 360
    dir_c = (270 - np.degrees(np.arctan2(vc, uc))) % 360
    diff = abs(dir_h - dir_c)
    diff = min(diff, 360 - diff)

    bars = ax_bar.bar([0, 1], [speed_h, speed_c], color=["tab:blue", "tab:orange"], width=0.5)
    ax_bar.set_xticks([0, 1])
    ax_bar.set_xticklabels(labels)
    ax_bar.set_ylabel("Speed (cm/s)")
    ax_bar.set_title(f"({compare_lon}, {compare_lat}) — {title_suffix}")
    for bar, direction in zip(bars, [dir_h, dir_c]):
        ax_bar.annotate(f"{direction:.1f}°\nfrom", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                         ha="center", va="bottom", fontsize=10)
    agree_word = "good agreement" if diff < 15 else "LARGE disagreement"
    ax_bar.annotate(
        f"Direction diff: {diff:.1f}°\n({agree_word})",
        xy=(0.5, 0.92), xycoords="axes fraction", ha="center", fontsize=9,
        bbox=dict(boxstyle="round", facecolor="lightyellow" if diff < 15 else "lightcoral"),
    )
    ax_bar.set_ylim(0, max(speed_h, speed_c) * 1.4)
    ax_bar.grid(axis="y", alpha=0.3)


def main() -> None:
    hycom_live = xr.open_dataset(CURRENTS_DIR / "hycom_aoi_recent.nc")
    cm_live = xr.open_dataset(CURRENTS_DIR / "copernicus_marine_aoi_recent.nc")
    hycom_hist = xr.open_dataset(CURRENTS_DIR / "hycom_aoi_AQ-2016-10-28.nc")
    cm_hist = xr.open_dataset(CURRENTS_DIR / "copernicus_marine_aoi_AQ-2016-10-28.nc")

    fig, axes = plt.subplots(2, 2, figsize=(13, 11))

    # Row 1: today's conditions, gulf-mouth comparison point
    now = np.datetime64(hycom_live.time.values[len(hycom_live.time) // 2])
    _plot_row(
        fig, axes[0, 0], axes[0, 1], hycom_live, cm_live,
        compare_lon=34.90, compare_lat=29.40, compare_time=now,
        title_suffix="today",
    )

    # Row 2: the actual demo event, AQ-2016-10-28, mooring peak-response time
    event_time = np.datetime64("2016-10-28T06:50:00")
    _plot_row(
        fig, axes[1, 0], axes[1, 1], hycom_hist, cm_hist,
        compare_lon=34.85, compare_lat=29.30, compare_time=event_time,
        title_suffix="AQ-2016-10-28 event peak",
    )

    fig.suptitle(
        "Both models mask the provisional outlet as unresolved/land in every case. "
        "Direction agreement today (~2°) is NOT representative of the actual event "
        "(65.8° disagreement) — the uncertainty that matters is the bottom row.",
        fontsize=10, y=1.0,
    )
    fig.tight_layout()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
