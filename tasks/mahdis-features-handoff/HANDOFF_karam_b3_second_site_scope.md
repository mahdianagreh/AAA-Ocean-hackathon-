# Data needed: a real second site in scope — for Karam

**Blocks:** Phase 5, B3 — Cross-Site Transfer Learning (`tasks/phase5/02-mahdi.md` §3)
**Status:** out of scope, not built — `docs/HANDOFF_abd_2026-08-07_b3_scope.md`

## What's missing

B3 needs a real second coastal site to fine-tune Aqaba's model onto, and to test the
pipeline against — the task itself is explicit that a pipeline "tested" against an
invented bounding box isn't a shipped feature. Per Mahdi (7 Aug 2026): **the project's
scope is Aqaba only, for now.** There is no second site.

This is a different kind of gap from B1/B2 — not "the data doesn't exist," but "there
is nothing to fetch data *for* yet."

## Why this is your call, not mine

Adding a second site is a scope decision, not a data-sourcing task — it changes what
this project claims to cover, at a point in the schedule (5 build days, freeze 12 Aug)
where that has real cost elsewhere. You're the integration lead; this is a "does the
team want to do this" question before it's a "where do we get the data" question.

## What would unblock B3 if the answer is yes

Once a second site is real scope:
1. A bounding box for it, plus a site identifier — parameterized from day one, never
   hardcoded, same discipline `backend/src/config/spatial.py` already enforces for
   Aqaba.
2. Whatever "thin local data" the task expects to fine-tune on — even a small amount
   is the point of transfer learning, but *some* real data for that site, not zero.

## What "done" looks like

Either: a bounding box + site name + a pointer to that site's available data, or a
clear "not this phase" so B3 stays out of scope on record rather than silently
dropped.
