# OSM drainage evidence for outlet correction

**From:** Pulga (Workstream A+B) · **To:** Mahdi (terrain / outlets)  
**Source:** `data/processed/vectors/osm_aqaba.gpkg`, layer `drainage_features`  
**Extract:** Geofabrik `jordan-latest.osm.pbf`, clipped to the padded AOI  
**Features:** 200 drainage lines, of which 27 are tagged `tunnel=culvert`

> **Read this before using anything below.** Absence of a mapped drainage
> feature in OSM is **not** evidence that no channel exists. OSM completeness
> for drainage infrastructure in Aqaba is unverified and probably patchy. Only
> **positive** matches — a feature that IS mapped — are usable as corrections.
> Nothing here can be used to rule a channel out.

---

## 1. Mapped culverts, nearest the coast first

Culverts are the highest-value features in this extract: a DEM routes surface
flow *around* an embankment, while a culvert carries it *through*. Where a
culvert crosses the coastal highway, the true outlet is seaward of wherever the
DEM puts it.

| # | lat | lon | waterway | length m | dist to coast m | nearest road |
|---:|---|---|---|---:|---:|---|
| 1 | 29.47387 | 34.97942 | drain | 34 | 39 | شارع الملك حسين |
| 2 | 29.35519 | 34.96074 | river | 19 | 64 | — |
| 3 | 29.4872 | 34.98601 | stream | 55 | 79 | شارع الملك حسين |
| 4 | 29.41698 | 34.97764 | drain | 67 | 105 | — |
| 5 | 29.3748 | 34.96775 | canal | 39 | 475 | — |
| 6 | 29.51994 | 35.00984 | stream | 57 | 876 | شارع مكة |
| 7 | 29.47174 | 34.98896 | drain | 71 | 970 | — |
| 8 | 29.4287 | 34.98871 | stream | 36 | 1317 | — |
| 9 | 29.40566 | 34.99083 | drain | 51 | 1662 | — |
| 10 | 29.55609 | 34.98928 | stream | 66 | 1790 | — |
| 11 | 29.565 | 34.97905 | stream | 21 | 2091 | طريق الحدود |
| 12 | 29.57544 | 34.97582 | stream | 30 | 3163 | — |
| 13 | 29.55514 | 35.02144 | canal | 44 | 3400 | Basman Street |
| 14 | 29.54884 | 35.02926 | canal | 110 | 3509 | شارع الحسين بن علي |
| 15 | 29.44015 | 35.01049 | stream | 124 | 3514 | — |
| 16 | 29.54658 | 35.03234 | canal | 20 | 3660 | — |
| 17 | 29.41228 | 35.01436 | stream | 33 | 3716 | — |
| 18 | 29.54471 | 35.03476 | canal | 88 | 3750 | — |
| 19 | 29.42536 | 35.01612 | stream | 47 | 3884 | — |
| 20 | 29.42035 | 35.01668 | stream | 41 | 3891 | — |
| 21 | 29.42868 | 35.01568 | stream | 42 | 3921 | — |
| 22 | 29.45676 | 35.03498 | stream | 57 | 5635 | — |
| 23 | 29.45746 | 35.03634 | stream | 42 | 5783 | — |
| 24 | 29.47598 | 35.06506 | stream | 43 | 7613 | — |
| 25 | 29.5669 | 35.08029 | river | 42 | 8806 | الطريق الصحراوي |
| 26 | 29.62227 | 35.02463 | drain | 47 | 9745 | — |
| 27 | 29.62194 | 35.0259 | drain | 14 | 9782 | — |

## 2. Drainage features within 1500 m of the shoreline

These are the candidate outlet positions — a mapped channel this close to the
sea is most likely reaching it.

| lat | lon | name | waterway | culvert | intermittent | dist to coast m |
|---|---|---|---|---|---|---:|
| 29.53055 | 35.00025 | — | stream |  | yes | 0 |
| 29.35598 | 34.96023 | — | river |  | yes | 0 |
| 29.47423 | 34.97907 | — | drain |  |  | 0 |
| 29.55064 | 34.9789 | — | canal |  |  | 0 |
| 29.3959 | 35.03737 | وادي النويبع | stream |  | yes | 0 |
| 29.55378 | 34.97858 | — | stream |  | yes | 6 |
| 29.47387 | 34.97942 | — | drain | yes |  | 39 |
| 29.51947 | 35.00531 | وادي الشلالة | stream |  | yes | 52 |
| 29.35519 | 34.96074 | — | river | yes | yes | 64 |
| 29.41664 | 34.97611 | — | drain |  | yes | 69 |
| 29.48724 | 34.98568 | — | stream |  | yes | 69 |
| 29.47166 | 34.98374 | — | drain |  | yes | 73 |
| 29.4872 | 34.98601 | — | stream | yes | yes | 79 |
| 29.321 | 35.00117 | — | river |  | yes | 80 |
| 29.41698 | 34.97764 | — | drain | yes | yes | 105 |
| 29.48724 | 34.99047 | — | stream |  | yes | 133 |
| 29.41523 | 34.97896 | — | drain |  | yes | 164 |
| 29.41604 | 34.99641 | — | stream |  | yes | 176 |
| 29.37439 | 34.96617 | — | canal |  |  | 211 |
| 29.41844 | 34.97895 | — | drain |  | yes | 243 |
| 29.51474 | 35.00419 | — | ditch |  |  | 320 |
| 29.3748 | 34.96775 | — | canal | yes |  | 475 |
| 29.37474 | 34.97355 | — | canal |  |  | 514 |
| 29.51526 | 35.0057 | — | ditch |  |  | 522 |
| 29.40718 | 34.98306 | — | drain |  |  | 712 |
| 29.4285 | 34.98611 | — | stream |  | yes | 859 |
| 29.51994 | 35.00984 | وادي الشلالة | stream | yes | yes | 876 |
| 29.52216 | 35.02369 | وادي الشلالة | stream |  | yes | 932 |
| 29.47174 | 34.98896 | — | drain | yes | yes | 970 |
| 29.4654 | 35.01446 | — | drain |  | yes | 1038 |
| 29.37042 | 34.97411 | — | canal |  |  | 1121 |
| 29.4426 | 34.99803 | — | stream |  | yes | 1144 |
| 29.3714 | 34.9747 | — | canal |  |  | 1166 |
| 29.37634 | 34.97614 | — | canal |  |  | 1174 |
| 29.37022 | 34.97468 | — | canal |  |  | 1176 |
| 29.37525 | 34.97587 | — | canal |  |  | 1181 |
| 29.37524 | 34.97601 | — | canal |  |  | 1200 |
| 29.37475 | 34.97613 | — | canal |  |  | 1225 |
| 29.37547 | 34.9763 | — | canal |  |  | 1227 |
| 29.4287 | 34.98871 | — | stream | yes | yes | 1317 |
| 29.37629 | 34.9777 | — | canal |  |  | 1320 |
| 29.43365 | 34.99984 | — | stream |  | yes | 1351 |
| 29.40691 | 34.98916 | — | drain |  |  | 1436 |

## 3. Named wadis in the extract

Named features are worth checking by hand — a named wadi is usually a real,
locally-recognised channel rather than an incidental ditch.

| name | lat | lon | waterway | dist to coast m |
|---|---|---|---|---:|
| وادي النويبع | 29.3959 | 35.03737 | stream | 0 |
| وادي الشلالة | 29.51947 | 35.00531 | stream | 52 |
| وادي الشلالة | 29.51994 | 35.00984 | stream | 876 |
| وادي الشلالة | 29.52216 | 35.02369 | stream | 932 |
| נחל שחורת | 29.60268 | 34.98292 | stream | 5274 |
| وادي اليتيم | 29.61292 | 35.04721 | river | 7329 |
| وادي اليتيم | 29.57879 | 35.1228 | river | 8642 |
| وادي اليتيم | 29.5669 | 35.08029 | river | 8806 |
| Wadi Umran | 29.52383 | 35.13633 | stream | 12617 |

## 4. DEM flow paths vs OSM drainage

**STATUS: PENDING — blocked on Mahdi's DEM flow paths.**

This section compares each mapped OSM drainage feature against the
DEM-derived flow network and lists the ones that fall outside a
50 m buffer of any modelled flow path — those are
the candidate outlet corrections.

It runs automatically as soon as a flow-path file exists at either:

- `data/processed/vectors/flow_paths.gpkg`
- `data/processed/dem/flow_paths.gpkg`

Re-run: `.venv/bin/python scripts/osm_drainage_report.py`

Sections 1-3 above need nothing from anyone and are final.
