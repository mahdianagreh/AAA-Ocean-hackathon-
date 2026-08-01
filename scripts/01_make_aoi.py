"""Create the folder structure and write the MARINE area of interest.

The project needs two extents, not one:

  terrain_aoi   land side - must cover the FULL contributing catchments.
                Derived from data by scripts/02_provisional_catchments.py,
                not guessed here. Wadi Yutum reaches ~90 km inland, so a
                coastal-strip box would cut off most of its drainage area.

  marine_aoi    sea side - the coastal water the plume can reach within
                ~24 h. Set here by hand.

  aqaba_aoi     union of the two, written by script 02. This is the box
                referenced in tasks/00-contracts.md.

Download using the union box or wider. Clip to the relevant extent at
analysis time, not download time.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# W, S, E, N in EPSG:4326.
# Jordan's coast runs ~29.35-29.55 N at lon ~34.96-35.00. The box reaches
# west and south into the Gulf far enough to hold a 24 h plume at typical
# northern-Gulf current speeds.
MARINE_BBOX = (34.80, 29.25, 35.05, 29.60)

DIRS = [
    "data/aoi",
    "data/raw/dem",
    "data/raw/hydro",
    "data/processed/dem",
    "data/processed/vectors",
    "data/processed/features",
    "data/interim",
    "docs",
]


def bbox_feature(bbox, name, note):
    w, s, e, n = bbox
    return {
        "type": "Feature",
        "properties": {"name": name, "note": note, "bbox": list(bbox)},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        },
    }


def write_geojson(path, feature):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature]}, indent=2) + "\n"
    )
    print(f"wrote {path.relative_to(ROOT)}")


def main():
    for d in DIRS:
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)
        (p / ".gitkeep").touch()

    write_geojson(
        ROOT / "data/aoi/marine_aoi.geojson",
        bbox_feature(
            MARINE_BBOX,
            "aqaba_marine_aoi",
            "Plume and reef extent. UNCONFIRMED - verify seaward reach against "
            "a 24 h drift at northern-Gulf current speeds.",
        ),
    )

    w, s, e, n = MARINE_BBOX
    print(f"marine AOI  {(e - w) * 111 * 0.87:.0f} km x {(n - s) * 111:.0f} km")
    print("\nnext: scripts/02_provisional_catchments.py writes terrain_aoi + aqaba_aoi")


if __name__ == "__main__":
    main()
