# Data needed: real satellite-visible plume masks — for Abd

**Blocks:** Phase 5, B1 — Automated Plume Segmentation Model (`tasks/phase5/02-mahdi.md` §1)
**Status:** flagged, not built — `docs/HANDOFF_abd_2026-08-07_b1_data.md`

## What's missing

A segmentation model needs real examples: a satellite image of the sea after a flood,
paired with a human-drawn (or otherwise confirmed) outline of where the sediment plume
actually was. The count of usable examples in this project today is **zero** — not
"a few," zero — and it's confirmed as a physical impossibility for the one event this
project has ground truth for:

- `docs/event_audit.md` §3 — final NO-GO verdict. No plume visible in Sentinel-2
  (2016-11-02) or an independent Landsat 8 pass (2016-11-01), because the plume
  dispersed in ~31 hours (per the mooring) — faster than either satellite's revisit
  gap. The plume was gone before any satellite passed overhead.
- The one file that looks like it could be training data,
  `observed_plume_PROVISIONAL.gpkg`, is dead — confirmed nothing in `backend/src/` or
  `frontend/src/` reads it.
- Checked the new `raw 2` data drop (8 Aug) for anything satellite/plume-related.
  Nothing — it's rainfall/soil/currents data, no optical imagery at all.

## Why this has to come from you, not me

You own Component C (plume/particle transport) and already did the rigorous
satellite QC that established the NO-GO — you're the one person who'd know if there's
a path here I haven't seen: a public dataset of labelled sediment plumes from *other*
coastlines that could bootstrap a general-purpose segmenter, a different Aqaba event
with better satellite timing, or confirmation that this genuinely doesn't exist
anywhere accessible.

## What would unblock B1 if it arrives

Either of:
1. **A real satellite pass that actually caught a plume** — this event or a different
   one, anywhere with a documented sediment discharge and a satellite image taken
   while it was still visible.
2. **A public, labelled dataset** of turbid-water/sediment-plume masks from other
   coastlines — even if not Aqaba-specific, enough to pre-train a segmenter that could
   then be fine-tuned on whatever Aqaba data exists (which today is still zero, but a
   pre-trained model needs less local data to fine-tune than to train from scratch).

## What "done" looks like

A file path (or dataset name) and, ideally, a rough count of usable image/mask pairs.
I can take it from there — schema design and model training are ready to go the
moment there's something real to point them at.

## If neither exists

Say so. That's a complete, useful answer too — it means B1 stays flagged for this
phase, honestly, rather than half-built against data that was never coming.
