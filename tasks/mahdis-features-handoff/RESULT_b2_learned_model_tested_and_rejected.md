# B2 result: tested with real data, learned model rejected — not a data gap anymore

Closes [`HANDOFF_karam_b2_transmission_loss_data.md`](HANDOFF_karam_b2_transmission_loss_data.md)
and [`RESPONSE_karam_b2_transmission_loss_data.md`](RESPONSE_karam_b2_transmission_loss_data.md).
Reproducible in full: `scripts/31_test_learned_transmission_loss.py`.

## What happened with the data Karam found

Cataldo et al. (2010)'s extracted tables gave `computed_tl_m3_per_km` — a volume-loss
*rate*, not the 0–1 *fraction* our `transmission_loss` actually is. The paper never
tabulates each storm's inflow volume directly, but it does print each storm's "Model
#1" predicted TL/km, which is a pure deterministic function of inflow volume alone
(`TL/km = 1.02 × Vol^0.75`). That's exactly invertible — recovered the real inflow
volume for every storm this way, then computed a genuine fractional transmission
loss: `(measured TL/km × reach length) / inflow volume`.

Result: **58 real, exact fractional-τ examples** across 12 systems and 3 independent
studies (Walnut Gulch excluded — its 30 storms span 4 different, unidentifiable reach
lengths; Cheyenne River SD excluded — no physical characteristics on record).

## What happened when a model was actually fit to it

Tested 7 feature combinations (catchment area, reach length, grain size D10, hydraulic
conductivity K, alone and combined) × 2 model types (linear, random forest), each
validated by **leave-one-system-out** — the same discipline as the runoff model's LOCO,
never letting a model see a system's own data before predicting for it.

**Every single one scored worse than just predicting the mean transmission loss across
all systems.** Negative R² throughout (−0.04 to −0.71).

**Why:** transmission loss varies enormously *within* a single system, storm to storm
— Cimarron River OK ranges from 0.25 to 1.11 across its 10 storms, despite every one
sharing identical area/grain-size/conductivity/reach-length. That within-system spread
(mean 0.38) is comparable to the spread *between* different systems' averages (0.46).
Static per-catchment characteristics cannot explain storm-to-storm variance by
definition, and here storm-to-storm variance is most of what there is to explain.

## The decision

**Not building a learned transmission-loss model.** This is a different, stronger
answer than the original flag — that said "no data exists to test this." This says
"real data was found, tested honestly, and a per-catchment learned estimate does not
outperform the flat borrowed range." Shipping one anyway would mean presenting a
negative-skill model as an improvement, which is the exact failure mode this project
exists to avoid.

`transmission_loss_basis` stays `"negev_proxy"` unconditionally — already shipped
(Phase 4/5), needs no further change. `sediment_proxy.TRANSMISSION_LOSS_BASIS` and its
"learned" branch remain exactly as documented; "learned" is not dead code waiting to be
finished, it's a real option this result closes out.

## What would change this

Not more literature of this same kind — this result held across three independent
studies and 12 real systems. What could change it: per-storm *dynamic* data (storm
size, intensity, antecedent conditions) rather than static catchment characteristics,
since that's what the within-system spread points at as the real driver. That's a
materially different, harder ask than the original one, and not pursued here without
it being requested.
