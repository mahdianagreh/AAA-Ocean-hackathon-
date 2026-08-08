# B1's data assumption doesn't hold — flagging before building anything

Mahdi, 7 August 2026. Not a criticism of the Phase 5 plan — this is exactly the kind of
thing that's easy to miss when writing nine feature specs at once. Flagging per your own
rule: no figure, no test → assumed, not verified. This one turned out to be assumed.

## What B1 (`tasks/phase5/02-mahdi.md` §1) currently says

> "the training set is whatever masks have accumulated so far — **almost certainly one
> digit's worth of events**. A model trained on a handful of masks is a first pass, not
> a validated segmenter."

## What's actually true, sourced from your own prior work

The real number is **zero**, and it's not a temporary gap — it's a confirmed physical
impossibility for this project's one validated event:

- `docs/HANDOFF_abd_2026-08-06.md` (§4) and `docs/event_audit.md` §3 ("Go / no-go —
  FINAL, pixel-level QC complete") record a **final NO-GO verdict**: no plume is visible
  in Sentinel-2 (2016-11-02) or an independent Landsat 8 pass (2016-11-01), for a
  documented physical reason — the plume dispersed in ~31 hours (per the mooring), faster
  than either satellite's revisit gap. Not clouds, not a processing bug. The plume was
  gone before any satellite passed overhead, and no amount of re-trying fixes that for
  this event.
- `observed_plume_PROVISIONAL.gpkg` — the one file that superficially looks like it could
  seed a training set — is dead. Your own audit confirmed nothing in `backend/src/` or
  `frontend/src/` reads it anymore; only its original generator script does.
- `backend/src/models/plume_segmentation.py`'s own docstring already states the
  conclusion this implies: *"Deliberately not a segmentation model — the Aqaba-specific
  labeled set is far too small for that to mean anything."* That decision was already
  made, for the reason B1 is now proposing to build past.

## Why this matters before any code gets written

A model "trained" on zero real examples doesn't produce a rough first pass — it produces
something that looks like a trained AI model while carrying no real signal, which is
precisely the "plausible output, no error" failure mode this project has spent five
phases guarding against elsewhere. Shipping a confidence score off that would be
decorative, not evidence.

## What I'd suggest instead, once you've had a look

Not building this without your sign-off first, per your note. The path that doesn't
require data that doesn't exist:

1. Build the mask-storage schema now (`human_reviewed`, `agreement_score`, etc.) —
   genuinely useful, costs nothing today, ready the moment real masks exist (a future
   real event with better satellite timing, or a B3 second site).
2. Wire the **existing, already-built** spectral-anomaly detector
   (`plume_segmentation.py`'s probability raster → polygon extraction) into its own
   `model_versions.jsonl` row, with real per-pixel confidence from that raster. That's
   the honest version of "confidence per generated mask" the current data actually
   supports.
3. Any dashboard copy says **zero confirmed masks**, not "a handful" — and states plainly
   that a trained segmenter isn't a defensible claim yet.

## The open question, back to you

Does B1's scope get revised given this, or is there context I'm missing — masks from
outside this project, a public dataset, something in flight I haven't seen — that would
change the picture? Either answer is fine; just didn't want to build toward a training
set that isn't there.
