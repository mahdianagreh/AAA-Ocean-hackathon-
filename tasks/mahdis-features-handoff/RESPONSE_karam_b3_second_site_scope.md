# Response: B3 second-site scope — decided, not silently dropped

Answers [`HANDOFF_karam_b3_second_site_scope.md`](HANDOFF_karam_b3_second_site_scope.md).

## Decision

**Not this phase. Project scope stays Aqaba-only.** With 4 build days left before
the 12 Aug freeze, adding a real second site now — a real bounding box, real local
data, a genuinely tested fine-tuning run, not an invented placeholder — carries real
schedule risk against everything else still open in Phase 5/6. This is a scope call,
made deliberately, not a gap that went unanswered.

## What this means for B3 concretely

- Build and test the **pipeline itself** against a placeholder/synthetic bounding box
  if that's useful groundwork — the task file already distinguishes "the pipeline
  runs" from "the pipeline is validated on a real second site," and scaffolding
  against a placeholder is fine as long as it's labelled as scaffolding, never
  presented as a tested transfer-learning result.
- The "model maturity" badge (0 validated events for any second site, since there is
  no second site) is the honest state to ship, not a badge implying B3 was
  demonstrated end-to-end.
- Any dashboard copy or slide should say "Aqaba-only in this phase" plainly, same
  language as this decision — not soften it to "not yet added" in a way that implies
  it's still pending discovery.

## If this decision needs revisiting

A second site becomes a legitimate ask again once schedule pressure eases (post-freeze,
or a future phase) — the requirements from the original handoff still stand then: a
real bounding box, a site identifier (new, separate from `AQ-*`/`R-*` per
`tasks/00-contracts.md` §2), and at least thin real local data to fine-tune on.
