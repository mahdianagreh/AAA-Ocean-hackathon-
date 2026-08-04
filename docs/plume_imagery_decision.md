# Plume imagery — what we generate, and what we never generate

**Decided 4 August 2026.** Recorded because it is the kind of decision that gets quietly
reversed by someone trying to make a screen look better, and because the reasoning is worth
more than the rule.

---

## The rule

| Slot | Imagery | Why |
|---|---|---|
| **Hero / pitch slide** | AI-generated illustration, **visibly labelled** | Sets the stakes. Nobody mistakes a hero image for data. |
| **Prediction output** | **Real satellite photo + the model's own output drawn on it** | This is where an observation would go. It has to be one. |
| Map, validation panel, provenance panel, RAG corpus | **Never generated** | These are the credibility surfaces. |

Generated files live in `frontend/public/illustration/` — **never** `frontend/public/basemap/`
or `public/fixtures/`, both of which mean "derived from real repo artefacts". Every one
carries the label *"Artistic illustration — not model output, not satellite imagery."*

---

## Why not generate the prediction image

The request was reasonable: the model predicts a flood, so show a picture of where the mud
goes, satellite-style. The obvious implementation is a diffusion model.

It fails for a specific reason, not a squeamish one. **A diffusion model has never seen
Aqaba.** It does not know the coastline, where `AQ-O01` sits, or how far a plume reaches. It
would produce a confident, well-composed, *wrong* place — and because the output looks like
satellite imagery, in this domain that reads as **observation**. Not a misreading; the
natural reading.

That puts a fabricated observation exactly where our real evidence goes, in a project whose
single strongest claim is:

> *The satellite could not see the plume, so we said so, and validated against a mooring
> instead.*

You cannot make that claim on one slide and show a generated satellite image on the next.
And it is worse than a fabricated number would be: numbers get audited, images get believed.

## The empirical argument, which settled it

The alternative was prototyped the same afternoon. The **first** render of real geometry put
the plume over Aqaba's city centre, the airport and a golf course — because the particle
engine was still a synthetic stub returning concentric `sqrt(t)` circles with no knowledge
of the coast.

That fault had been sitting in the API returning six perfectly reasonable-looking polygons.
No test caught it. It became obvious the moment it was drawn on a real coastline.

**A generated image would have drawn a plausible coast and hidden it completely.**

So: real geometry fails loudly when the data is wrong, and generated imagery fails silently.
On a project whose recurring failure mode is *plausible wrong output with no error*, that is
the whole argument.

`clip_to_sea=False` exists on the renderer only so that failure can be demonstrated
deliberately.

---

## What the real path gives up, and what it does not

It does not look worse. It looks **more** convincing, because it is recognisably Aqaba
rather than a generic tropical coast — the port, the city, the wadi mouth in their real
positions.

What it costs is nothing at runtime: `scripts/fetch_basemap_raster.py` bakes the imagery once
to a JPEG plus a bounds sidecar, so `backend/src/rendering/plume_map.py` needs no network, no
tile stack and no API key. Verified by running the container on an isolated Docker network
where it cannot resolve the tile server — the endpoint still returned 200 with the real
basemap.

Every image carries its provenance in two places: a footer burned into the pixels, and
response headers.

```
X-ReefShield-Generated-Imagery: none
X-ReefShield-Plume-Source: stub | particle-engine
X-ReefShield-Basemap: esri-worldimagery-baked | absent
```

The burned-in footer matters because images get screenshotted into slides, where they lose
every bit of surrounding context except their own pixels.

---

## Generating the hero images

Local, not an API. Cost was never the constraint — roughly $2 for the ~40 generations it
takes to get 6 keepers — but a meter makes you settle early, and there is no LLM or image key
in `.env`, with credential rotation already outstanding.

Draw Things on Apple Silicon, Flux.1 Schnell or Dev. Aqaba is **desert**: bare tan rock to
the waterline. Diffusion models drift toward palm trees and Caribbean blues, so say
`arid, barren desert coast, no vegetation`.

Match the drone top-down framing of `data/raw/photos/kinnet_canal_site/` — 14 real
photographs of the actual outlet — so the set reads as one place.

And **do not aim for photorealism at satellite scale.** Slightly stylised is safer: if it is
too convincing, someone will take it for data, which is the one outcome that costs us.

---

## What we already have, and should use before generating anything

| | |
|---|---|
| The outlet | ✅ 14 real drone photos, `data/raw/photos/kinnet_canal_site/` |
| Proof a plume happened | ✅ Kalman mooring: 2.18 g/L, ~31 h, −1.75 ‰ (19σ) |
| Where the plume goes | ✅ `GET /api/v1/plume/map` — real imagery, real model output |
| The plume *in the water* | ❌ no photo exists — the satellite missed it |
| Coral being smothered | ❌ no photo from the event |

Only the last two are worth generating. Which gives the honest framing:

> *Here is the real outlet. Here is the sensor data proving the plume. And here is an
> illustration of what it looked like in the water — because no satellite passed over in
> time.*

That turns the weakness into the centrepiece.
