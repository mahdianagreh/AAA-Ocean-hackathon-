# Transmission loss — the slider range, for Pulga and Ali

Mahdi, Phase 4 task 3. `transmission_loss: 0.525` is already a real field in every
`predict_one()` response — the parameter exists and the audit's guess was right. What
doesn't exist yet: an API parameter that lets a caller *change* it, and a documented
range for the slider that will call it.

---

## What it means, in one sentence

**Transmission loss is the fraction of a flood's water — and the sediment it carries —
that soaks into the dry wadi streambed before ever reaching the coast.** It's the
`(1 − τ)` term in the sediment formula (`backend/src/models/sediment_proxy.py`): higher
transmission loss means less of what fell as rain actually arrives at the reef, everything
else held equal. Put this sentence (or your own version of it) directly next to the
slider — this is exactly the kind of number that reads as an arbitrary UI toy unless the
caption explains why moving it changes the score.

## The range to bound the slider to

Three different ranges exist in the code, and they are not interchangeable:

| range | value | what it is |
|---|---|---|
| `TAU_LITERATURE` | 13.2% – 98% | full range across arid catchments generally — includes environments nothing like Aqaba |
| **`TAU_NEGEV`** | **20% – 85%** | **the closest studied desert analog to Aqaba's wadis — use this for the slider** |
| `TAU_DEFAULT` | 52.5% | the Negev midpoint — used because it's the nearest documented setting, **not because it was measured here** |
| code-level validation | `[0%, 100%)` | `SedimentParams.validate()`'s hard floor/ceiling — a sanity check, not a claim of physical plausibility |

**Bound the slider to the Negev range, 20%–85%, not the wider literature range and
not the code's technical `[0, 100)` limit.** Letting a user drag it to 0% ("nothing
ever soaks in") or 99% ("almost everything soaks in") would let the UI assert something
no cited source supports for this environment. If there's a reason to expose the wider
literature band too (e.g. an "extreme scenario" toggle), label it explicitly as the
broader, less-Aqaba-specific range — don't blend the two silently.

## What's actually missing, concretely

`SedimentProxy.with_transmission_loss(tau)` already exists and does exactly what a
scenario slider needs — it returns a new proxy instance at a different τ, nothing
mutated. **Nothing in the API currently accepts τ as a request parameter** — it's only
ever read back as an output at the fixed default. Pulga: this needs a bounded field
(min 0.20, max 0.85, default 0.525) threaded through to
`sediment.with_transmission_loss(tau)` before the formula runs, not a UI control that
changes nothing server-side.
