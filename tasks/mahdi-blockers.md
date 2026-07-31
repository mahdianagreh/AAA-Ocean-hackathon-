# Mahdi's Blocking Tasks — What They Are and Why They Matter

**Project:** ReefShield Aqaba
**Owner:** Mahdi
**Purpose:** four of my tasks block other teammates. This explains each one in plain terms — what it is, why the project needs it, and what breaks if it's late or wrong.

---

## Summary

| # | Task | Who is blocked | Deadline |
|---:|---|---|---|
| 1 | AOI bounding box | **Everyone** | Day 1 |
| 2 | Shared Google Earth Engine project | Pulga, Abd | Day 1 |
| 3 | Catchment polygons + `catchment_id` | Karam, Pulga | Day 3 |
| 4 | Outlet coordinates | Nizar, Abd | Day 4 |

My other three sources — SRTM, MERIT Hydro, HydroSHEDS — block nobody. They are my own cross-checks and a presentation layer, so they can slip without hurting anyone.

---

## 1. AOI bounding box

### What it is

A rectangle drawn on the map with four numbers: a west and east longitude, a south and north latitude. It says "this is the study area — Aqaba and the piece of the Gulf in front of it."

It gets saved as a single small file, `data/aoi/aqaba_aoi.geojson`, and committed to the repo so there is exactly one copy.

### Why it's needed

Every teammate downloads from a different source, and every one of those sources covers the whole planet. Nobody wants global data, so each download gets cut down to the study area. That cut has to be made with the **same rectangle every time.**

### What breaks without it

If Karam clips rainfall to one box and Pulga clips land cover to a slightly different one, the two grids don't line up. Then:

- "average the rainfall inside this catchment" silently uses the wrong cells
- overlaying reef zones on a plume map puts things in the wrong place
- nothing throws an error — the numbers just come out quietly wrong

That's the dangerous kind of bug: no crash, no warning, just results that look fine and aren't. Which is why it's a Day 1 task and why there's one committed file rather than five people each typing coordinates.

### Also worth getting right

The box has to reach **far enough out to sea** to contain a plume drifting for 24 hours. If it only covers the coastline, the plume simulation runs particles straight off the edge of the map.

---

## 2. Shared Google Earth Engine project

### What it is

A Google Cloud project with Earth Engine switched on. Earth Engine is Google's satellite data platform — it already stores most of the datasets this project needs, on Google's own servers.

### Why it's needed

Normally you download data, then process it on your laptop. Some of these datasets are enormous, and downloading them would take days and fill the disk.

Earth Engine flips that around: **you send the code to the data.** You write a request like "give me the coral habitat layer for this rectangle," Google runs it on their machines, and you get back a small file with just your answer.

### Who needs it

- **Pulga** — Allen Coral Atlas (the coral habitat maps) is only practically accessible this way
- **Abd** — Sentinel-2 and HLS imagery, as the fast route for experimenting
- **Me** — MERIT Hydro
- **Karam** — ERA5-Land, as an alternative access route

### What breaks without it

Pulga can't get the reef zones. No reef zones means no exposure score, and the exposure score is the entire point of the platform. Abd's imagery work also gets much slower.

### Why it's mine

It only needs to exist once, and one person has to create it and invite everyone. Registration can take time to approve, so it goes on Day 1 even though nobody uses it until Day 4.

---

## 3. Catchment polygons + `catchment_id`

### What it is

A **catchment** is all the land that drains into one wadi. Rain falling anywhere inside it eventually flows to the same channel and out the same point on the coast.

I produce these as polygons — outlines on a map — three to five of them, each with a permanent name: `AQ-C01`, `AQ-C02`, and so on.

### Why it's needed

Rain doesn't matter to this project as a per-pixel number. What matters is **how much rain landed on the area that feeds one particular wadi**, because that's what decides whether that wadi floods.

So the catchment polygon is the unit of measurement for the whole project. Everyone measures things *inside* it:

- **Karam** averages rainfall inside it → "40 mm fell on the Wadi Yutum catchment in 3 hours"
- **Pulga** measures land cover inside it → "74% of that catchment is bare ground"
- **Pulga** averages soil properties inside it → clay and sand fractions
- **I** measure its shape → area, steepness, drainage density

### Why the ID matters as much as the polygon

All those measurements end up in separate tables that have to be stitched together into one row per catchment. The `catchment_id` is the key that stitches them.

If I rename `AQ-C01` to `AQ-C1` halfway through, every table that used the old name stops matching. So the naming scheme gets agreed once, up front, and never changes.

### What breaks without it

Karam can't turn rainfall into a per-catchment number, so there's no event table. Pulga's land and soil work has nothing to attach to. The runoff model has no rows to train on.

---

## 4. Outlet coordinates

### What it is

One point per catchment: the longitude and latitude where that wadi's channel reaches the sea. Four or five pairs of numbers, and they are the most consequential numbers I produce.

### Why it's needed

This is the exact spot where the land part of the story becomes the sea part. Sediment-loaded floodwater exits the wadi here and enters the Gulf here.

- **Nizar's plume simulation starts here.** It releases thousands of simulated particles at this coordinate and pushes them around with currents and wind. The release point *is* the outlet.
- **Abd's validation is anchored here.** He finds the real plume in a satellite image and checks whether it emerged where the model said it would. That check is meaningless if the outlet is wrong.

### What breaks if it's late or moves

Move the outlet 500 m along the coast and the plume drifts into a different reef zone. Every simulation run, every calibration, every validation comparison has to be redone.

That's why the deadline is Day 4 rather than "sometime": everything downstream of it is expensive to repeat.

### Why it's harder than it sounds

The elevation data I use is a **surface** model — it includes buildings, walls, and road embankments as if they were hills. The last stretch before the coast is the most built-up part of Aqaba, so the computer will route water *around* structures that water actually flows through, past, or under.

That means the final outlet position needs checking by eye against satellite imagery, and cross-checking against Pulga's OpenStreetMap layer where culverts and storm drains are mapped. It's the one part of my stream that can't be fully automated.

---

## The order this implies

1. **Day 1** — commit the AOI box, create the GEE project. Neither takes long; both unblock everyone.
2. **Day 2** — download the DEM and run the flow-routing chain.
3. **Day 3** — catchment polygons out to Karam and Pulga.
4. **Day 4** — outlets checked against imagery and OSM, then published to Nizar and Abd. **Locked from here.**

My stream depends on nobody, so there's no reason for any of this to be late.
