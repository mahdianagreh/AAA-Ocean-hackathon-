# Mooring coordinate derivation — AQ-2016-10-28

**Owner:** Abd · Workstream 5 (Marine Transport & Validation)
**Status:** derived assumption, not a reported coordinate. Read the uncertainty section
before using this point for anything more precise than "the head of the Gulf."

This file exists because Kalman et al. (2025) never states the mooring's position as a
decimal latitude/longitude — only *"~250 m offshore the Kinnet Canal outlet, 13 m depth"*
(paper text, line 207 of the extracted full text; see §1 below). Per the project's
source-vs-derived rule (`docs/event_dates.md` §3), a number we computed is never presented
as a number the paper reported. This document is the computation, so anyone can check it.

---

## 0. The correction this derivation surfaces

**The Kinnet Canal discharges on the Eilat (Israel) shoreline, not the Jordan/Aqaba
side.** Direct quote from the paper (page 8 of the extracted text): *"Flash floods
reaching the sea through the Kinnet Canal (discharge located on Eilat shoreline)."* The
Kinnet watershed is explicitly **trans-national** — it spans both countries — but the
canal itself, and therefore the mooring 250 m offshore it, sits on the Israeli side of the
head of the Gulf, not at Mahdi's Jordanian `AQ-O01` (Wadi Yutum) pour point.

The two are close (1.40 km apart, computed in §3) and almost certainly describe two
different engineering definitions of the same trans-national drainage system — Mahdi's
DEM pour point is where flow exits the Jordanian portion of the catchment; the Kinnet
Canal is the shared channel's actual sea outlet, downstream of both countries' contributing
area, on the Israeli side of the border. **Do not treat `AQ-O01`'s coordinate as the
mooring's location.** They are related, not identical.

This also matters for the particle engine: the physical release point that generated the
observed mooring signal is the Kinnet Canal mouth (§3), not necessarily coincident with
wherever `outlets.gpkg` places `AQ-O01`. For calibration purposes (Part 2 of `05-abd.md`)
release at the Kinnet Canal mouth derived here; `AQ-O01`/`AQ-O05` remain the two release
points for the forward-looking scenario demo per the task file, since that is the
Jordanian, defensible outlet the project is built around.

---

## 1. What the paper actually says

Extracted from `data/raw/literature/kalman_et_al_2025_fulltext_ATC1.pdf` via
`pdftotext -layout` (poppler-utils, installed locally to do this extraction):

> "An instrumented mooring station was anchored ~250 m offshore in front of the Kinnet
> Canal ... offshore the Kinnet outlet at 13 m water depth."

No decimal coordinate appears anywhere in the text. The only geolocated information is
**Fig. 1b** — a labelled regional map showing the mooring's position relative to Eilat,
Aqaba, and the watershed boundary, with axis tick marks at longitude 35.0°/35.6° and
latitude 29.4°/29.8°.

---

## 2. Digitizing Fig. 1b

Steps actually run, in order, so they can be repeated or checked:

1. Rendered page 7 of the PDF (the page containing Fig. 1) at 600 DPI with
   `pdftoppm -png -r 600 -f 7 -l 7`.
2. Cropped to the map panel and located the four axis tick marks by pixel-intensity
   scanning (dark tick marks against a white margin, immediately outside the map frame's
   grey border) rather than reading them off by eye:
   - Longitude 35.0° → pixel x ≈ 630; longitude 35.6° → pixel x ≈ 1545 (915 px / 0.6°)
   - Latitude 29.8° → pixel y ≈ 696; latitude 29.4° → pixel y ≈ 1385.5 (689.5 px / 0.4°,
     y increasing downward as latitude decreases)
3. Located the map's location marker (a small solid red rectangle sitting at the
   coastline, distinct from the red triangular "Aqaba" city-label pin above it) by color
   thresholding (`R > 180, G < 80, B < 80`) and took its pixel centroid.
4. Applied the linear pixel→degree mapping from step 2 to the marker centroid.

**Result — the raw digitized point:**

```
lon = 34.97593
lat = 29.52773
```

**This number is not the recommended coordinate.** Two things make it too imprecise to
use directly:

- The marker itself is a solid rectangle covering **~30 × 14 px ≈ 1.9 km × 0.9 km** at
  this map's scale (~64 m/px) — it was drawn as an area indicator, not a precise pin, and
  Fig. 1b is a small illustrative panel embedded in a two-column PDF, not a
  survey-grade map.
- Sampling `depth_utm36n.tif` (Pulga's real bathymetry, EPSG:32636, 50 m grid) at this raw
  point returns **−120 m** — nowhere near the reported 13 m. Whatever this point marks,
  it is not sitting at the mooring's actual depth, which means the raw digitization is not
  usable on its own for anything depth-sensitive.

---

## 3. Anchoring to real coastline data and re-deriving the offset

Rather than trust the schematic figure's precision, the raw digitized point was used only
to identify **which stretch of coastline** the canal outlet is near, then re-anchored to
Pulga's actual `coastline.gpkg` (EPSG:4326, reprojected to EPSG:32636 for all distance
math per the project's CRS contract):

1. **Snap to the real coastline.** Nearest point on the `shoreline` layer to the raw
   digitized marker:
   ```
   lon = 34.98336, lat = 29.53956
   ```
   Distance from the raw marker to this snap point: **1,496.5 m**. This distance is the
   single largest source of error in this whole derivation, and is used directly as the
   uncertainty radius in §4 — it is not a guessed number, it is the measured disagreement
   between the figure's schematic basemap and the project's own surveyed coastline.

2. **Find the seaward direction.** Local coastline tangent estimated from two points ±20 m
   along the shoreline from the snap point; the perpendicular (normal) direction was
   resolved into "seaward" by testing which side falls inside the `water` polygon.
   Seaward bearing: **225° from north** (south-southwest), which is the direction directly
   into the Gulf at this part of the coast, not along it.

3. **Offset 250 m seaward**, per the paper's stated distance:
   ```
   lon = 34.98151, lat = 29.53799
   ```

4. **Cross-check against real depth.** Sampling `depth_utm36n.tif` at this point returns
   **−15.34 m**. The paper reports **13 m**. A fine-grained scan along the same bearing
   shows the raster crosses from −10.37 m to −15.34 m at approximately **214 m** offshore
   — the 50 m grid does not resolve depth continuously, so "13 m" falls inside a single
   grid-cell step between those two values. **The reported depth and the reported distance
   agree with each other via this raster to within one grid cell.** That agreement is the
   strongest evidence in this whole derivation that the direction and general location are
   right, even though the raw figure digitization on its own was not.

**Recommended coordinate:**

```
lon = 34.98151
lat = 29.53799
uncertainty_radius_m = 1500
depth_at_point_m = -15.34   # bathymetry raster value; paper reports -13 m
```

---

## 4. Uncertainty, stated plainly

**Uncertainty radius: 1.5 km**, taken as the measured distance between the raw
figure-digitized point and its nearest match on the project's real coastline (§3, step 1).
This is deliberately the *largest* of the error sources identified, not an average or a
smaller component of it:

| Source | Size | Included in the 1.5 km figure? |
|---|---|---|
| Figure-to-coastline disagreement (schematic basemap vs. surveyed coastline) | 1,496 m | **Yes — this is the number used** |
| Marker footprint (the drawn rectangle itself) | ~1.9 km × 0.9 km | Subsumed — same order of magnitude |
| Seaward bearing choice | small (bathymetry cross-check in §3.4 supports it) | Not separately added |
| "~250 m" offshore distance itself (paper says "~", not exact) | ±50–100 m | Not separately added — small next to the 1.5 km term |

Do not report this coordinate to more precision than the radius implies. "Approximately
34.98°E, 29.54°N, ±1.5 km, at the head of the Gulf near the Kinnet Canal mouth on the
Eilat shoreline" is the honest statement. A sixth decimal place would be fabricated
precision.

**Independent triangulation, for confidence, not for precision:** the coastline-snapped
point (§3 step 1) sits **1.40 km** from `AQ-O01` (Wadi Yutum's Jordanian DEM pour point,
34.97073, 29.54560 — `outlets.gpkg`). That three independent position estimates — the raw
figure digitization, the coastline-snap, and Mahdi's unrelated DEM-derived pour point —
all cluster within ~1.5 km of each other at the head of the Gulf near the Israel–Jordan
border is a reasonable sanity check that no gross error (wrong watershed, wrong country,
transposed lat/lon) is present. It is not a claim that any two of them are the same point.

---

## 5. Machine-readable summary

```yaml
mooring_position_AQ-2016-10-28:
  recommended:
    lon: 34.98151
    lat: 29.53799
    crs: EPSG:4326
    uncertainty_radius_m: 1500
    basis: derived — see docs/mooring_coordinate_derivation.md
  derivation_steps:
    - digitized_from: "Kalman et al. 2025, Fig. 1b (page 7 of kalman_et_al_2025_fulltext_ATC1.pdf)"
      raw_point: {lon: 34.97593, lat: 29.52773}
      method: "pixel-tick calibration (35.0/35.6 lon, 29.8/29.4 lat) + red-marker color threshold centroid"
    - snapped_to: "data/processed/vectors/coastline.gpkg (layer=shoreline)"
      snapped_point: {lon: 34.98336, lat: 29.53956}
      snap_distance_m: 1496.5
    - offset_seaward_m: 250
      bearing_deg_from_north: 225
      bearing_method: "local coastline normal, resolved seaward via water polygon containment"
  depth_cross_check:
    source: data/processed/bathymetry/depth_utm36n.tif
    depth_at_recommended_point_m: -15.34
    depth_reported_by_paper_m: -13
    distance_where_raster_crosses_13m_offshore_m: 214
    note: "50 m nominal grid, ~450 m true resolution per docs/pitch_limitations.md §4 — agreement within one grid-cell step"
  correction_surfaced:
    finding: "Kinnet Canal discharge is on the Eilat (Israel) shoreline, not the Jordan/Aqaba side"
    source: "Kalman et al. 2025, page 8: 'discharge located on Eilat shoreline'"
    distance_to_AQ-O01_m: 1395.7
    implication: "Do not treat AQ-O01 (Wadi Yutum, Jordan pour point) as the mooring location. Related trans-national watershed, different national outlet."
  tooling_note: "poppler-utils (pdftoppm/pdftotext) installed locally via 'brew install poppler' to extract this — not previously a project dependency."
```

## 6. Rules for consumers of this file

1. **Never present the recommended coordinate as a reported one.** It is derived; say so
   every time it appears, per `docs/event_dates.md` §3's precedent.
2. **Never drop the uncertainty radius.** A point without its 1.5 km radius is a claim of
   precision this derivation does not support.
3. **`AQ-O01` and this mooring coordinate are not interchangeable.** See §0.
4. If someone obtains the paper's underlying GPS log or supplementary data with an exact
   coordinate, replace this derivation entirely rather than reconciling it — a real
   measurement supersedes a derived one, it does not average with it.
