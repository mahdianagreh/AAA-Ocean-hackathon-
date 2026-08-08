# B2's training data doesn't exist either — same shape as B1, different ingredient

Mahdi, 7 August 2026. Flagging before building the model, same as B1 — the
`transmission_loss_basis` field it also asks for is built and safe to ship regardless
(details below); the regression model is not.

## What B2 (`tasks/phase5/02-mahdi.md` §2) asks for

> "Regression model predicting per-catchment transmission loss from terrain slope,
> soil texture, and drainage density."

## What that needs, and what actually exists

A regression needs real examples: catchment features paired with a **measured**
transmission-loss value, across enough catchments to learn a real relationship. I
searched the whole repo for anything resembling this. There isn't one.

The only transmission-loss numbers anywhere are two fixed ranges in
`backend/src/models/sediment_proxy.py`:

```python
TAU_LITERATURE = (0.132, 0.98)   # arid catchments generally
TAU_NEGEV      = (0.20, 0.85)    # closest studied analog
```

No citation in the code, and — the part that matters here — no underlying table of
"catchment X had these features and this measured loss." Two ranges are not a training
set. There's nothing to regress against, for any catchment, anywhere in this project.

This is the same shape as B1's finding (`docs/HANDOFF_abd_2026-08-07_b1_data.md`): not
thin data, no data. A model "trained" on nothing would produce a number that looks
learned and isn't — the same failure mode, for the same underlying reason.

## What's already built, safe, and doesn't wait on this

B2 separately asks for a `transmission_loss_basis: "learned" | "negev_proxy"` field so
every response is honest about which source produced the number. That part needs no
training data — it's just a true label. Built and shipped today:

- `sediment_proxy.TRANSMISSION_LOSS_BASIS = "negev_proxy"` — unconditional, since
  "learned" has no implementation.
- `RunoffPrediction.transmission_loss_basis` (`schemas.py`), right next to the existing
  `transmission_loss` field, not a parallel one.
- Set on every real-path response in `runoff_model.py`, `None` on the stub path (matches
  `transmission_loss`'s own None-on-stub behaviour).
- Threaded into `/api/v1/exposure/calculate`'s `formula_terms` too, per Standing Law
  rule 10 — the basis travels with the number, not just in a log.

Every value in the system today — default 0.525 or a user-moved slider — is a point on
the borrowed Negev range, never a per-catchment estimate. `transmission_loss_basis`
says `"negev_proxy"` every time, honestly, until that changes.

## The open question, back to you

Same as B1: is there a real measured-tau dataset I haven't found — a paper with a table
of catchment properties vs. measured transmission loss across multiple sites — that
would make the regression model buildable? If one exists, point me at it and this
becomes buildable. If not, B2's model half stays flagged, same as B1, until either a
dataset shows up or the scope changes.
