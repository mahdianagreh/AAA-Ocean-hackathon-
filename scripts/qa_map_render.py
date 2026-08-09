#!/usr/bin/env python3
"""QA figure for the frontend map render — country borders and label hygiene.

Not a computed figure like the rest of this directory: the subject is a browser
render, so the PNG is captured by Playwright and framed here with its caption,
which is what makes it self-explanatory once it is pasted into a slide.

    npx playwright test  # produces the capture
    python3 scripts/qa_map_render.py --shot /path/to/final-default.png
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

import qa_common

CAPTION = (
    "Frontend map after the 9 Aug fix. WAS WRONG: (1) no political geography at all — a "
    "four-country basin drawn as one landmass; (2) Wadi Rum tourism labels ('rock arch', "
    "'Thamudic inscriptions', 'Siq Trail') strewn across the catchment, because "
    "frontend_basemap.py classified every OSM tourism=attraction as kind='dive' and "
    "TERRAIN_AOI reaches ~90 km inland — 36 of 46 'dive sites' sat 5-45.7 km from the sea, "
    "which also contaminated p4-B Dive Site Safety; (3) 'Petra' labelled 79 km away. "
    "FIXED: Natural Earth 10m admin-0 borders + bilingual country/city labels, committed "
    "offline; dive = sport=scuba_diving only (46 -> 7, all in the water); a coastal flag "
    "(<=5 km from MARINE_AOI) stamped on places and protected areas and filtered in the "
    "style. NOT a bug, verified: the large polygon is the real AQ-C01 at 4453.3 km2 "
    "(contract says 4,453 +/-4%) and catchments are already individually risk-coloured at "
    "0.22 opacity — AQ-C01 is simply 69x the next catchment."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    args = ap.parse_args()
    shot = Path(args.shot)
    if not shot.exists():
        print(f"missing {shot}")
        return 1

    img = mpimg.imread(shot)
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(w / 150, h / 150 + 1.1), dpi=150)
    ax.imshow(img)
    ax.set_axis_off()
    ax.set_title("Map render: country borders present, tourism labels gone",
                 fontsize=10, loc="left")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.16)
    qa_common.save_fig(fig, "map_01_borders_and_label_hygiene", CAPTION, "Frontend")
    qa_common.write_manifest_md()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
