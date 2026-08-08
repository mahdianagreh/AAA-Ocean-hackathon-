# Post-storm damage estimate — verified safe, and the copy to use

Mahdi, Phase 4 task 5. This was flagged the riskiest item on the list, so here's both
halves: what I checked, and the exact wording to put in the UI.

## Verified: no tonnage figure is reachable, for any event

Checked every field `predict_one()` returns, on two different days (the anchor event
and an unrelated high-rainfall day), plus every field in `schemas.py` and the exposure
engine. Only two sediment fields ever come back: `sediment_index` (an unbounded,
unitless number — useful for ranking, not a mass) and `sediment_class`
(`Low`/`Medium`/`High`/`Extreme`). Neither is a tonnage. The only place `24,400`
appears anywhere in the backend is a static citation of the published paper's own
measurement for the one historical event — not a number computed live for whichever
storm is on screen. **No bug to close. Do not build a feature that reports a tonnage
for any event other than the one it's already correctly not doing this for.**

## The copy, in judge-readable language

> We know the real amount of sediment from exactly one storm — a published mooring
> study measured it directly for the October 2016 flood. That single measurement lets
> us calibrate the *scale* of our formula for that one event, but it can't tell us
> whether the formula scales correctly for a storm of a different size — that would
> take multiple real measurements, and we only have one. So for every storm, we show a
> **relative severity class** (Low / Medium / High / Extreme) rather than a specific
> tonnage — except for the one documented event, where the number is a real citation,
> not a model output.

Use "relative severity class," never "estimated tonnage" or "damage estimate," in any
UI copy for any event other than the anchor. If a tonnage-sounding feature name
("Post-Storm Damage Estimate") ships, the number it shows must still be the class, or
the name is promising something the number underneath doesn't support.
