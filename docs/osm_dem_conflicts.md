# OSM drainage evidence for outlet correction

**From:** Pulga (Workstream A+B) · **To:** Mahdi (terrain / outlets)  
**Source:** `data/processed/vectors/osm_aqaba.gpkg`, layer `drainage_features`  
**Extract:** Geofabrik `jordan-latest.osm.pbf`, clipped to the padded AOI  
**Features:** 1402 drainage lines, of which 46 are tagged `tunnel=culvert`

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
| 1 | 29.47387 | 34.97942 | drain | 34 | 33 | شارع الملك حسين |
| 2 | 29.4872 | 34.98601 | stream | 55 | 82 | شارع الملك حسين |
| 3 | 29.35519 | 34.96074 | river | 19 | 82 | — |
| 4 | 29.41698 | 34.97764 | drain | 67 | 140 | — |
| 5 | 29.3748 | 34.96775 | canal | 39 | 478 | — |
| 6 | 29.51994 | 35.00984 | stream | 57 | 879 | شارع مكة |
| 7 | 29.47174 | 34.98896 | drain | 71 | 962 | — |
| 8 | 29.4287 | 34.98871 | stream | 36 | 1326 | — |
| 9 | 29.40566 | 34.99083 | drain | 51 | 1679 | — |
| 10 | 29.55609 | 34.98928 | stream | 66 | 1804 | — |
| 11 | 29.565 | 34.97905 | stream | 21 | 2104 | طريق الحدود |
| 12 | 29.57544 | 34.97582 | stream | 30 | 3166 | — |
| 13 | 29.55514 | 35.02144 | canal | 44 | 3432 | Basman Street |
| 14 | 29.44015 | 35.01049 | stream | 124 | 3531 | — |
| 15 | 29.54884 | 35.02926 | canal | 110 | 3538 | شارع الحسين بن علي |
| 16 | 29.54658 | 35.03234 | canal | 20 | 3701 | — |
| 17 | 29.41228 | 35.01436 | stream | 33 | 3726 | — |
| 18 | 29.54471 | 35.03476 | canal | 88 | 3796 | — |
| 19 | 29.42536 | 35.01612 | stream | 47 | 3887 | — |
| 20 | 29.42035 | 35.01668 | stream | 41 | 3894 | — |
| 21 | 29.42868 | 35.01568 | stream | 42 | 3923 | — |
| 22 | 29.45676 | 35.03498 | stream | 57 | 5638 | — |
| 23 | 29.45746 | 35.03634 | stream | 42 | 5786 | — |
| 24 | 29.47598 | 35.06506 | stream | 43 | 7664 | — |
| 25 | 29.5669 | 35.08029 | river | 42 | 8850 | الطريق الصحراوي |
| 26 | 29.62227 | 35.02463 | drain | 47 | 9769 | — |
| 27 | 29.62194 | 35.0259 | drain | 14 | 9807 | — |
| 28 | 29.60086 | 35.16645 | stream | 81 | 18005 | Desert Highway |
| 29 | 29.80248 | 35.0679 | stream | 22 | 29803 | Jordan Valley Highway |
| 30 | 29.9275 | 35.12065 | river | 22 | 44564 | Jordan Valley Highway |
| 31 | 29.99417 | 35.14806 | stream | 35 | 52404 | Jordan Valley Highway |
| 32 | 29.94921 | 35.35041 | stream | 10 | 57465 | — |
| 33 | 29.94678 | 35.36572 | stream | 18 | 58142 | — |
| 34 | 29.96124 | 35.35869 | stream | 10 | 59013 | — |
| 35 | 30.10537 | 35.38592 | stream | 14 | 73703 | — |
| 36 | 30.24973 | 35.20859 | stream | 16 | 81189 | Jordan Valley Highway |
| 37 | 30.20159 | 35.36559 | stream | 12 | 81930 | — |
| 38 | 30.20515 | 35.36479 | stream | 12 | 82242 | — |
| 39 | 30.21992 | 35.36682 | stream | 12 | 83785 | — |
| 40 | 30.2285 | 35.3635 | stream | 14 | 84484 | — |
| 41 | 30.2393 | 35.35851 | stream | 16 | 85346 | — |
| 42 | 30.23943 | 35.35846 | stream | 15 | 85355 | — |
| 43 | 30.24041 | 35.35751 | stream | 12 | 85415 | — |
| 44 | 30.17784 | 35.77511 | stream | 31 | 103774 | — |
| 45 | 30.1424 | 35.8424 | stream | 22 | 106038 | — |
| 46 | 30.1157 | 35.87296 | stream | 24 | 106512 | — |

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
| 29.55378 | 34.97858 | — | stream |  | yes | 9 |
| 29.47387 | 34.97942 | — | drain | yes |  | 33 |
| 29.51947 | 35.00531 | وادي الشلالة | stream |  | yes | 55 |
| 29.47166 | 34.98374 | — | drain |  | yes | 57 |
| 29.48724 | 34.98568 | — | stream |  | yes | 72 |
| 29.4872 | 34.98601 | — | stream | yes | yes | 82 |
| 29.35519 | 34.96074 | — | river | yes | yes | 82 |
| 29.41664 | 34.97611 | — | drain |  | yes | 92 |
| 29.321 | 35.00117 | — | river |  | yes | 101 |
| 29.48724 | 34.99047 | — | stream |  | yes | 136 |
| 29.41698 | 34.97764 | — | drain | yes | yes | 140 |
| 29.41523 | 34.97896 | — | drain |  | yes | 187 |
| 29.41604 | 34.99641 | — | stream |  | yes | 197 |
| 29.37439 | 34.96617 | — | canal |  |  | 232 |
| 29.41844 | 34.97895 | — | drain |  | yes | 246 |
| 29.51474 | 35.00419 | — | ditch |  |  | 323 |
| 29.3748 | 34.96775 | — | canal | yes |  | 478 |
| 29.37474 | 34.97355 | — | canal |  |  | 517 |
| 29.51526 | 35.0057 | — | ditch |  |  | 525 |
| 29.40718 | 34.98306 | — | drain |  |  | 724 |
| 29.4285 | 34.98611 | — | stream |  | yes | 874 |
| 29.51994 | 35.00984 | وادي الشلالة | stream | yes | yes | 879 |
| 29.52216 | 35.02369 | وادي الشلالة | stream |  | yes | 934 |
| 29.47174 | 34.98896 | — | drain | yes | yes | 962 |
| 29.4654 | 35.01446 | — | drain |  | yes | 1030 |
| 29.4426 | 34.99803 | — | stream |  | yes | 1160 |
| 29.37042 | 34.97411 | — | canal |  |  | 1174 |
| 29.37634 | 34.97614 | — | canal |  |  | 1178 |
| 29.37525 | 34.97587 | — | canal |  |  | 1185 |
| 29.37524 | 34.97601 | — | canal |  |  | 1204 |
| 29.3714 | 34.9747 | — | canal |  |  | 1219 |
| 29.37475 | 34.97613 | — | canal |  |  | 1228 |
| 29.37022 | 34.97468 | — | canal |  |  | 1229 |
| 29.37547 | 34.9763 | — | canal |  |  | 1231 |
| 29.37629 | 34.9777 | — | canal |  |  | 1323 |
| 29.4287 | 34.98871 | — | stream | yes | yes | 1326 |
| 29.43365 | 34.99984 | — | stream |  | yes | 1360 |
| 29.40691 | 34.98916 | — | drain |  |  | 1446 |

## 3. Named wadis in the extract

Named features are worth checking by hand — a named wadi is usually a real,
locally-recognised channel rather than an incidental ditch.

| name | lat | lon | waterway | dist to coast m |
|---|---|---|---|---:|
| وادي النويبع | 29.3959 | 35.03737 | stream | 0 |
| وادي الشلالة | 29.51947 | 35.00531 | stream | 55 |
| وادي الشلالة | 29.51994 | 35.00984 | stream | 879 |
| وادي الشلالة | 29.52216 | 35.02369 | stream | 934 |
| נחל שחורת | 29.60268 | 34.98292 | stream | 5285 |
| وادي اليتيم | 29.61292 | 35.04721 | river | 7364 |
| وادي اليتيم | 29.61793 | 35.16398 | river | 8689 |
| وادي اليتيم | 29.5669 | 35.08029 | river | 8850 |
| Wadi Umran | 29.52264 | 35.13732 | stream | 12620 |
| وادي الغضيا | 29.31547 | 35.29432 | river | 32098 |
| נחל יטבתה | 29.83351 | 35.06221 | stream | 32646 |
| נחל שעלב | 29.95244 | 35.08845 | stream | 38915 |
| Great Siq | 29.57632 | 35.40892 | stream | 39833 |
| Wadi Aheimar | 29.98747 | 35.2377 | river | 40023 |
| وادي رم | 29.62289 | 35.43735 | stream | 41304 |
| Wadi Flajeh | 29.83216 | 35.46859 | stream | 49444 |
| נחל קטורה | 29.99463 | 35.08907 | stream | 49739 |
| وادي سلادح | 29.25689 | 35.51933 | river | 51653 |
| נחל חיון | 30.14909 | 35.00951 | stream | 52748 |
| Wadi eth Thilāja | 29.77746 | 35.5075 | wadi | 53178 |
| وادي عامود | 29.7695 | 35.55728 | wadi | 54030 |
| وادي القناصية | 29.72135 | 35.57181 | wadi | 56193 |
| Wadi Al-Seeq | 30.05537 | 35.22605 | river | 57692 |
| Wadi Rakiya | 30.02894 | 35.27351 | stream | 58640 |
| وادي ابا الحار | 29.26441 | 35.64957 | river | 59195 |
| وادي رابغ | 29.76841 | 35.58273 | wadi | 61220 |
| s | 30.02293 | 35.37525 | stream | 65074 |
| Wadi Gseib | 30.10791 | 35.21274 | stream | 65576 |
| Wadi Gseib | 30.11496 | 35.27392 | stream | 66613 |
| נחל הערבה | 30.22504 | 35.1479 | river | 68773 |
| נחל פארן | 30.22904 | 34.8053 | river | 69771 |
| Wadi Mshazza | 30.1588 | 35.29027 | stream | 72160 |
| Wadi al-Saif | 30.16765 | 35.286 | stream | 74964 |
| وادي الشبيكي | 29.22906 | 35.76709 | river | 76481 |
| Wadi Abu O-rouq | 30.21487 | 35.39859 | stream | 81102 |
| Wadi Sabra | 30.23412 | 35.32149 | stream | 81644 |
| נחל מנוחה | 30.29936 | 35.13456 | stream | 84792 |
| Wadi Sabra | 30.25693 | 35.39496 | stream | 85033 |
| Wadi Sabra | 30.24041 | 35.35751 | stream | 85415 |
| Wadi al-Tiben | 30.24988 | 35.41679 | stream | 88339 |
| Wadi Al-Raqi | 30.28963 | 35.4317 | stream | 92206 |
| قنات | 30.19706 | 35.69725 | canal | 99615 |

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
