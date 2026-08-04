# Illustration assets — generated imagery, and the rule that keeps it safe

Files here are **AI-generated illustrations**. They are the only generated imagery anywhere
in the product, and they are allowed only because of where they are *not*.

## The rule

**Allowed:** hero image, opening/pitch slide, anywhere the reader is plainly looking at
artwork.

**Never:** the map, the prediction output, the validation panel, the provenance panel, or
the RAG corpus. Those are the credibility surfaces.

Every image must carry a visible caption:

> Artistic illustration — not model output, not satellite imagery.

## Why the separation is strict

This directory is deliberately **not** `../basemap/` and **not** `../fixtures/`. Both of
those mean "derived from real repo artefacts", and Ali's own convention is that a fixture is
never invented. Keeping generated content in its own directory means the distinction survives
someone reorganising components a week from now.

The prediction picture is `GET /api/v1/plume/map` — a real Esri satellite photograph with the
model's own plume drawn on it, `X-ReefShield-Generated-Imagery: none`. That is what goes
where an observation belongs.

Full reasoning, including why generating the prediction image was rejected on evidence
rather than on principle: **`docs/plume_imagery_decision.md`**.
