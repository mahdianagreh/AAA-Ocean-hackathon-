# Mahdi's Phase 5 features — data still needed, by owner

Cross-referenced against `tasks/phase5/02-mahdi.md` tasks 1-4 (B1, B2, B3, B9) and the
`raw 2` data drop (8 Aug 2026), which resolved none of them — see
`docs/HANDOFF_abd_2026-08-07_b1_data.md`/`b2_data.md`/`b3_scope.md` for the original
flags this folder follows up on.

| Task | Feature | Status | Owner | Files |
|---|---|---|---|---|
| 1 | B1 — Plume segmentation | Flagged, still open — no satellite ever saw a plume, confirmed physically impossible for the anchor event | Abd | [`HANDOFF_abd_b1_plume_masks.md`](HANDOFF_abd_b1_plume_masks.md) |
| 2 | B2 — Learned transmission loss | **Closed — real data found, tested, learned model rejected** (negative skill vs. the flat borrowed range) | Karam | [`HANDOFF_karam_b2_transmission_loss_data.md`](HANDOFF_karam_b2_transmission_loss_data.md) → [`RESPONSE_karam_b2_transmission_loss_data.md`](RESPONSE_karam_b2_transmission_loss_data.md) → [`RESULT_b2_learned_model_tested_and_rejected.md`](RESULT_b2_learned_model_tested_and_rejected.md) |
| 3 | B3 — Cross-site transfer | **Closed — out of scope**, Aqaba-only this phase | Karam | [`HANDOFF_karam_b3_second_site_scope.md`](HANDOFF_karam_b3_second_site_scope.md) → [`RESPONSE_karam_b3_second_site_scope.md`](RESPONSE_karam_b3_second_site_scope.md) |
| 4 | B9 — Culvert/drainage detector | **Nothing — already unblocked** | — | not applicable |

B9 has no entry because it has no data gap: it formalizes a manual check
(`scripts/12_culvert_crosscheck.py`) that already runs on data already on disk. It's
listed here only so all four tasks are accounted for, not skipped silently.

B2's chain is worth reading in order: the original ask, then Karam's real dataset, then
the actual regression test against it (`scripts/31_test_learned_transmission_loss.py`)
— the ask was answered, and the answer that came back closed the question rather than
opening a model-building task.

Each handoff below states exactly what's missing, why Mahdi can't source it himself,
what it would unblock once it arrives, and what "done" looks like — so a returned
answer can be acted on immediately instead of triggering a second round of questions.
