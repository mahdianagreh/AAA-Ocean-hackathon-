# Data needed: a real measured-transmission-loss dataset — for Karam

**Blocks:** Phase 5, B2 — Learned Transmission-Loss Model (`tasks/phase5/02-mahdi.md` §2)
**Status:** flagged, model half not built — `docs/HANDOFF_abd_2026-08-07_b2_data.md`.
The honest part of B2 (`transmission_loss_basis` field) already shipped and needs
nothing further.

## What's missing

B2 asks for a regression model: predict per-catchment transmission loss from terrain
slope, soil texture, and drainage density. A regression needs real examples — a
catchment's features paired with its **measured** transmission loss — across enough
catchments to learn a real relationship, not five points fit to three-plus features.

That dataset does not exist in this project. The only transmission-loss numbers
anywhere are two fixed ranges in `backend/src/models/sediment_proxy.py`:

```python
TAU_LITERATURE = (0.132, 0.98)   # arid catchments generally
TAU_NEGEV      = (0.20, 0.85)    # closest studied analog
```

No citation attached in the code, and critically, no underlying table — just two
numbers. Checked the `raw 2` data drop (8 Aug) on the chance it held something: the
one lead that looked promising, `levenson_2020_sdb_thesis.pdf`, turned out to be
about **Satellite-Derived Bathymetry**, unrelated. Nothing else in that drop touches
transmission loss either.

## Why this has to come from you, not me

You've already done exactly this kind of work for this project — Kalman et al.
(2025)'s dated flood events, the Katz et al. citations, the corrected 21×/78× leakage
numbers — pulling real measurements out of the literature when the pipeline needed
them and nobody else had gone looking. This is the same kind of task: find a paper (or
set of papers) that measured transmission loss across multiple arid catchments *with*
their physical characteristics recorded, so there's something to regress against.

## What would unblock B2 if it arrives

A source — paper, dataset, technical report — with a **table**, not just a range:
catchment slope/soil/drainage density (or close enough proxies) next to a measured or
modelled transmission-loss value, for enough catchments (more than 5, ideally across
more than one study) that a regression means something. The original `TAU_LITERATURE`
range (0.132-0.98) must have come from somewhere — if you can trace that back to its
source paper(s), that's the first place to look.

## What "done" looks like

A citation (or several) and, ideally, the actual table extracted — even a photo of a
table from a paywalled PDF is enough, same as how Request 0 worked before. I can build
the regression the moment there's a real target to fit.

## If nothing exists

Also a complete answer. B2's model half stays flagged for this phase; the
`transmission_loss_basis: "negev_proxy"` field already ships today and says so
honestly on every response regardless.
