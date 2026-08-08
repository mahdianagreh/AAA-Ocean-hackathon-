# B3 — out of scope, not a data gap

Mahdi, 7 August 2026. Different shape from the B1/B2 flags — those were "the data
doesn't exist yet." This one is simpler: **the project's scope is Aqaba only, for now.**

B3 (`tasks/phase5/02-mahdi.md` §3) requires "one real or realistic second-site bounding
box" to fine-tune onto and test against. There is no second site in scope — building
the pipeline now means writing and "testing" a transfer-learning script against a
bounding box invented for the exercise, which isn't the "tested against one real or
realistic site" the task itself asks for; it's testing against nothing.

Not building this until there's an actual second site to point it at. Flagging now
rather than shipping a pipeline with nothing real behind it, or silently dropping the
task with no record of why.

If a second site becomes real scope later, the earlier discipline still applies:
parameterize by bounding box and site identifier from day one (same as
`backend/src/config/spatial.py`'s existing rule), never hardcode a second AOI the way
Aqaba's was before that contract existed.
