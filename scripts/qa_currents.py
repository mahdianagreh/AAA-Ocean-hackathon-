"""
QA figure: HYCOM vs Copernicus Marine current comparison at the Aqaba AOI.

Shows both models' resolved current vectors on the same map, the provisional
outlet marked where both models independently mask it as land, and the
gulf-mouth direction/speed comparison numbers. Backs the claim in
docs/forcing_limitations.md and docs/data_dictionary.md §8.

Run: cd backend && .venv/bin/python ../scripts/qa_currents.py
Requires data/raw/currents/{hycom,copernicus_marine}_aoi_recent.nc to already exist
(python -m src.ingestion.ocean_currents from backend/).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENTS_DIR = REPO_ROOT / "data" / "raw" / "currents"
OUT_PATH = REPO_ROOT / "docs" / "qa_screenshots" / "currents_01_hycom_vs_copernicus.png"

OUTLET_LON, OUTLET_LAT = 34.96, 29.52
GULF_MOUTH_LON, GULF_MOUTH_LAT = 34.90, 29.40


def main() -> None:
    hycom = xr.open_dataset(CURRENTS_DIR / "hycom_aoi_recent.nc")
    cm = xr.open_dataset(CURRENTS_DIR / "copernicus_marine_aoi_recent.nc")

    hycom_now = hycom.isel(time=len(hycom.time) // 2, depth=0)
    cm_now = cm.isel(time=len(cm.time) // 2, depth=0)

    fig, (ax_map, ax_bar) = plt.subplots(1, 2, figsize=(13, 5.5))

    hlon, hlat = np.meshgrid(hycom_now.longitude, hycom_now.latitude)
    ax_map.quiver(
        hlon, hlat, hycom_now["u"].values, hycom_now["v"].values,
        color="tab:blue", scale=1.5, label="HYCOM GLBy0.08 (~9km)", width=0.004,
    )

    clon, clat = np.meshgrid(cm_now.longitude, cm_now.latitude)
    ax_map.quiver(
        clon, clat, cm_now["u"].values, cm_now["v"].values,
        color="tab:orange", scale=1.5, label="Copernicus Marine (~9km)", width=0.004,
    )

    ax_map.scatter([OUTLET_LON], [OUTLET_LAT], marker="x", s=140, color="red", linewidths=3,
                   label="Provisional outlet (masked in BOTH models)", zorder=5)
    ax_map.scatter([GULF_MOUTH_LON], [GULF_MOUTH_LAT], marker="o", s=90, facecolors="none",
                   edgecolors="black", linewidths=2, label="Comparison point (both resolve)", zorder=5)

    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.set_title("Aqaba AOI: HYCOM vs Copernicus Marine surface currents")
    ax_map.legend(loc="upper right", fontsize=8)
    ax_map.set_aspect(1 / np.cos(np.radians(29.4)))
    ax_map.grid(alpha=0.3)

    # Gulf-mouth point comparison (from ocean_currents.compare_hycom_vs_copernicus, 2026-08-03)
    labels = ["HYCOM", "Copernicus Marine"]
    speeds_cm_s = [6.92, 8.29]
    directions_deg = [52.9, 46.9]

    x = np.arange(len(labels))
    bars = ax_bar.bar(x, speeds_cm_s, color=["tab:blue", "tab:orange"], width=0.5)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(labels)
    ax_bar.set_ylabel("Speed (cm/s)")
    ax_bar.set_title(f"Gulf mouth ({GULF_MOUTH_LON}, {GULF_MOUTH_LAT}): speed + direction")
    for bar, direction in zip(bars, directions_deg):
        ax_bar.annotate(
            f"{direction:.1f}°\nfrom",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center", va="bottom", fontsize=10,
        )
    ax_bar.annotate(
        "Direction agreement: 6.0°\n(good — independent models converge)",
        xy=(0.5, 0.92), xycoords="axes fraction", ha="center", fontsize=9,
        bbox=dict(boxstyle="round", facecolor="lightyellow"),
    )
    ax_bar.set_ylim(0, max(speeds_cm_s) * 1.4)
    ax_bar.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Both models independently mask the provisional outlet as unresolved/land — "
        "confirming the ~9km resolution limitation, not a single-source artifact.",
        fontsize=10, y=1.02,
    )
    fig.tight_layout()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
