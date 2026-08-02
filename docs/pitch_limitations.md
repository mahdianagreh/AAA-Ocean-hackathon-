# What our data can and cannot tell you

**ReefShield Aqaba · data foundation (land cover, soil, urban, reef habitat, bathymetry)**

This page is written for the judges, not for our own notebooks. Every limitation
below is one we found ourselves and chose to state, because a data platform that
overstates its inputs is worse than one that is modest about them — and because
anything we do not say here, someone will find during questions.

---

## The one-line version

We built a working sediment-to-reef data foundation for Aqaba from five open
datasets in two weeks. **Three of those five datasets are global models or global
products, not local measurements.** Our outputs are therefore a defensible *relative*
ranking of which catchments threaten which reefs — not an absolute prediction of how
much sediment lands where.

---

## 1. Our land cover is a single snapshot from 2021

ESA WorldCover gives us 10 m land cover for one epoch, 2021. There is no time series.

**What that means:** we model the February 2013 and October 2016 flood events using
2021 land cover. Aqaba grew between those dates. Any change in bare ground or built-up
area across that decade is invisible to us, and it runs in the direction that matters
— more development means more runoff.

**What we would do with more time:** Landsat-based change detection across 2013–2021
to at least bound the error.

---

## 2. Our soil data is a global model, not Aqaba's soil

SoilGrids is a machine-learning product trained on global soil profiles. Nobody has
sampled the soil in our catchments for this project.

**If you ask us how we know Aqaba's soil texture, the honest answer is: we don't.**
We use SoilGrids as a *relative* erodibility ranking between our own catchments,
where the model's systematic biases largely cancel. We never quote a clay percentage
as a measured local property.

We did verify the data is internally consistent — clay + sand + silt sums to exactly
100.00%, bulk density falls in the real-soil range of 1.09–1.46 kg/dm³, and organic
carbon is appropriately low for desert at ~12 g/kg. That confirms we are reading the
product correctly. It does not make it a local measurement.

**Phase 2:** field sampling at a handful of wadi outlets would anchor the ranking.

---

## 3. We could not obtain GEBCO, and we say so

Our brief specified GEBCO 15 arc-second bathymetry. **Every programmatic route to
GEBCO is currently closed** — its WCS service returns empty capabilities, its download
endpoint rejects automated requests, and the published tile paths return 404. It is
available only through an interactive web form.

Rather than stall or quietly fake it, we substituted **GMRT**, a bathymetric synthesis
whose deep-water source in this region is GEBCO itself. We then checked it two ways:

- GMRT agrees with NOAA's independent global relief mosaic on the basin's deepest
  point to within **0.2 metres**.
- Our derived coastline agrees with OpenStreetMap's independently traced coastline to
  a **median of 62 metres** — about one pixel.

**We kept the file named `gmrt_aqaba.tif`, not `gebco_aqaba.tif`.** Mislabelling it
would have been the easy path and a genuine integrity failure. The pipeline
automatically prefers real GEBCO the moment someone downloads it by hand.

---

## 4. Our bathymetry cannot see the reef shelf

This is the most important limitation on this page.

The effective resolution of our depth data is about **450 metres**. The Gulf of Aqaba
has one of the steepest coastal drop-offs in the world — the reef shelf is often only
tens of metres wide before the seabed plunges past 200 m.

**Consequence:** our depth grid claims −372 m only 100 m offshore in places. That is
an interpolation artefact, not a real slope. So:

- Our plume model is credible at **basin scale** and as a "particles stop at the
  shore" boundary.
- It is **not** credible for reef-scale depth, small channels, or harbour structures.
- We therefore did **not** derive our reef zone boundaries from depth contours, even
  though that would have looked more rigorous. Deriving a reef edge from an
  interpolation artefact would have dressed up a guess as a measurement.

Our reef zone widths are an explicit, documented 250 m assumption.

---

## 5. Our reef sensitivity weights are assumptions, not data

Every reef zone carries `sensitivity_weight = 1.0`. **That is a placeholder, and it is
labelled as one inside the data file itself**, not just in a footnote — the column
`sensitivity_weight_status` literally reads
`PLACEHOLDER_PENDING_MARINE_SCIENTIST`.

Allen Coral Atlas maps *habitat*, not *sensitivity*. Deciding that one reef is twice
as vulnerable as another requires marine-science expertise this team does not have.

We did find one piece of real evidence that bears on it: the **Aqaba Marine Park**
boundary, which we extracted from OSM. Four of our eight zones fall 67–85% inside the
legally protected reserve. We stored that overlap as a measured percentage and
**deliberately did not convert it into a weight** — that conversion is a scientist's
judgement, not ours.

**If our exposure ranking looks confident, that confidence comes from the sediment
side, not the sensitivity side.**

---

## 6. Allen Coral Atlas maps shallow reef only

Once the real habitat export lands, it still only covers optically shallow reef.
Deeper habitat is not in the product, so our exposure map is **silent** about it —
which is different from saying it is safe.

---

## 7. OpenStreetMap tells us what is mapped, not what exists

We use OSM for roads, buildings and — most valuably — 27 mapped culverts that correct
where wadis actually reach the sea. A DEM routes water *around* a road embankment; a
culvert carries it *through*.

**But OSM completeness in Aqaba is unverified.** So we adopted a one-way rule: a
mapped feature is positive evidence, and an unmapped one is *no* evidence. We never
use OSM's silence to rule a channel out. Our conflict report for the terrain lead
states this in its own header so it cannot be misread downstream.

---

## 8. What we would fix first, given another week

1. Field-sample soil at the main wadi outlets — turns limitation 2 from a caveat into
   a calibration.
2. Get high-resolution nearshore bathymetry — this single fix unlocks reef-scale
   plume behaviour and would let us replace the 250 m assumption in limitation 4.
3. Sit down with an Aqaba marine scientist for one hour and replace limitation 5's
   placeholder weights with real ones.

---

## Why we are telling you all this

We caught **five silent bugs** in our own data during this build: reef zones placed on
dry land, a nodata value that would have turned particle positions into non-numbers,
sea pixels being read as zero-clay soil, 1.46 hectares of double-counted reef, and a
set of distances measured in the wrong projection and overstated by 15%.

None of those five would have thrown an error. Every one was caught by insisting that
each processing step produce a picture we had to look at. That is the same discipline
behind every caveat on this page — and it is the reason we would rather show you the
limits of this data than have you discover them for us.
