# 03 · Information Architecture

**Status:** scaffold — filled during Phase 1–2 · **Owner:** Ali

Structure and open questions are recorded now so nothing is forgotten; the detail lands as the shell
and the vertical slice are built.

---

## 1 · One screen

Concept §15.3's entire demo storyboard is eight scenes on one screen. There is no second page except
the in-app limitations text and the provenance panel, and both are overlays rather than routes.

Routes: `/` (the map) · `/specimen` (component gallery, dev only).

## 2 · Three modes

| Mode | Shows | Time range |
|---|---|---|
| **Historical** | Reconstruct `AQ-2016-10-28` — rainfall, runoff, plume, exposure, then validation | The event window, fixed |
| **Forecast** | Today's live GFS/GEFS/IFS → per-catchment risk | Now → +N hours, rolling |
| **Scenario** | User changes parameters and watches risk change | Inherits the base mode's range |

> **Forecast must work on a dry day and show a correctly low number.** A system that only demos
> during a storm is not demoable. The empty-ish state is a first-class design problem, not a fallback.

**Mode switching preserves the time cursor where the ranges overlap** and clamps otherwise, rather
than resetting to zero. Resetting loses the user's place mid-demo.

## 3 · Layout regions

- [ ] Masthead — brand, mode switcher, language toggle, connection state
- [ ] Map — the dominant region, never smaller than half the viewport
- [ ] Side rail — risk cards, layer toggles, legend
- [ ] Scenario drawer — six controls, opens over the rail in Scenario mode
- [ ] Time bar — full width beneath the map, drives every time-varying layer
- [ ] Overlays — provenance, limitations, assistant

All positioning uses logical properties. See [`06-bilingual-rtl.md`](06-bilingual-rtl.md) §2.

## 4 · Map layer stack and z-order

Bottom to top. To be fixed in Phase 1 and not renegotiated later.

- [ ] Basemap (custom vector style) / satellite (optional toggle)
- [ ] Bathymetry isobaths
- [ ] Coastline
- [ ] Catchments — filled by runoff risk
- [ ] Rainfall intensity over catchments
- [ ] Plume relative-density contours — **time-varying**. Not probabilities; see
      [`07-data-contracts.md`](07-data-contracts.md) §4
- [ ] Reef zones — filled by exposure score
- [ ] Outlets — sized by upstream area
- [ ] Mooring marker
- [ ] Model-grid overlay (the honesty device, optional)
- [ ] Dive sites, Marine Park boundary (optional, both in `osm_aqaba.gpkg`)
- [ ] Labels
- [ ] Attribution control — always visible

## 5 · Open questions

- [ ] Does the side rail collapse on narrow viewports, or does the map?
- [ ] Risk cards: all zones always, or only those above `low`?
- [ ] Does the scenario drawer block the map, or push it?
- [ ] Where does the `AQ-O04` enclosed-harbour caveat surface — on the outlet, the card, or both?
