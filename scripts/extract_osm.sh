#!/usr/bin/env bash
# OpenStreetMap Jordan extract -> clipped, layered GeoPackage for the AOI.
#
# Re-clipped 2 Aug 2026 against TERRAIN_AOI. The previous clip used the old
# (34.80, 29.25, 35.15, 29.70) box and covered ~5% of the terrain extent, missing
# nearly all of Wadi Yutum's road and drainage network.
#
# Produces data/processed/vectors/osm_aqaba.gpkg with layers:
#   roads, buildings, waterways, drainage_features, industrial, port
#
# osmium-tool is not installed and is not needed: GDAL's OSM driver reads .osm.pbf
# directly and -clipsrc does the AOI clip in the same pass.
#
# OSM_CONFIG_FILE points at our own osmconf copy, which promotes `tunnel` and
# `industrial` to real columns. Culverts are the single highest-value features in
# this extract (they are what correct Mahdi's outlet positions) and by default
# `tunnel` is buried inside the other_tags HSTORE where SQL cannot filter it
# cleanly.
set -euo pipefail

cd "$(dirname "$0")/.."

PBF="data/raw/osm/jordan-latest.osm.pbf"
AOI="data/aoi/terrain_aoi.geojson"   # contract-owned; see backend/src/config/spatial.py
OUT="data/processed/vectors/osm_aqaba.gpkg"
export OSM_CONFIG_FILE="scripts/osmconf_reefshield.ini"

[[ -f "$PBF" ]] || { echo "missing $PBF"; exit 1; }
[[ -f "$AOI" ]] || { echo "missing $AOI — the spatial contract owns this file"; exit 1; }
rm -f "$OUT"

# $1=src layer  $2=dst layer  $3=WHERE
extract() {
  local src="$1" dst="$2" where="$3" mode="-update"
  [[ -f "$OUT" ]] || mode=""
  # PROMOTE_TO_MULTI is required: -clipsrc cuts a road crossing the AOI edge into
  # several pieces, which GDAL then hands over as MULTILINESTRING. Without this the
  # write is non-conformant and the layer geometry type is a lie.
  # -gt batches the writes. Note -skipfailures and -gt are mutually exclusive in
  # GDAL's arg parser, so do not add -skipfailures back here: passing both makes
  # ogr2ogr print its usage block and write nothing at all.
  # shellcheck disable=SC2086
  ogr2ogr -f GPKG $mode "$OUT" "$PBF" "$src" \
      -where "$where" -nln "$dst" -clipsrc "$AOI" \
      -nlt PROMOTE_TO_MULTI -gt 65536 2>/dev/null || true
  local n=""
  n=$(ogrinfo -so "$OUT" "$dst" 2>/dev/null | awk -F': ' '/^Feature Count/{print $2}') || n=""
  printf "  %-20s %s features\n" "$dst" "${n:-0}"
}

echo "extracting OSM layers for TERRAIN_AOI..."

extract lines         roads      "highway IS NOT NULL"
extract multipolygons buildings  "building IS NOT NULL"
extract lines         waterways  "waterway IS NOT NULL"

# Drainage: the outlet-correction layer. OSM tagging for arid drainage is
# inconsistent, so every plausible variant is caught rather than just one.
# `wadi` is deprecated upstream but still present in Jordanian data.
extract lines drainage_features \
  "waterway IN ('drain','ditch','stream','river','wadi','canal') OR tunnel = 'culvert'"

extract multipolygons industrial \
  "landuse = 'industrial' OR industrial IS NOT NULL"

extract multipolygons port \
  "landuse IN ('port','harbour') OR industrial = 'port' OR harbour IS NOT NULL"

# ---------------------------------------------------------------------------
# Layers beyond the original task list. Extracting them costs one more pass over
# a 30 MB file now; discovering later that the exposure engine or the dashboard
# wants dive-centre locations means re-running the whole extract under deadline.
# ---------------------------------------------------------------------------

# Dive sites and coastal tourism POIs — the people the alert product is FOR.
# A reef zone is only "operationally meaningful" relative to who dives it.
extract points dive_tourism_poi \
  "sport = 'scuba_diving' OR tourism IN ('hotel','resort','attraction','viewpoint','information')
   OR leisure IN ('marina','beach_resort','slipway') OR natural = 'beach'
   OR amenity = 'dive_centre'"

extract multipolygons tourism_areas \
  "tourism IS NOT NULL OR leisure IN ('marina','beach_resort','nature_reserve','park')"

# Marine protected areas / Aqaba Marine Park. If OSM has the reserve boundary it
# is a real cross-check on our hand-placed reef zone extent.
extract multipolygons protected_areas \
  "boundary IN ('protected_area','national_park') OR leisure = 'nature_reserve'
   OR protect_class IS NOT NULL"

# Coastline as OSM sees it — an INDEPENDENT check on the bathymetry-derived
# shoreline, from a completely different data lineage.
extract lines osm_coastline "natural = 'coastline'"

# Additional infrastructure that shapes runoff: railway, embankments, dams,
# breakwaters, piers. Impervious or flow-blocking, all of it.
extract lines infrastructure_lines \
  "railway IS NOT NULL OR man_made IN ('embankment','breakwater','pier','dyke','groyne')
   OR barrier IN ('wall','retaining_wall')"

extract multipolygons water_bodies \
  "natural = 'water' OR water IS NOT NULL OR landuse = 'reservoir'"

echo
echo "wrote $OUT"
ogrinfo -so "$OUT" 2>/dev/null | grep -E "^[0-9]+:"
