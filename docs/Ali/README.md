# Ali — Workstream 6

Two folders, two different kinds of document. The distinction matters and is easy to lose once they
sit side by side.

| Folder | What it is | App surface? | In the RAG corpus? |
|---|---|---|---|
| [`frontend/`](frontend/) | Build documentation for the interface — design language, tokens, contracts, phases | It *describes* the app | **No** |
| [`research/`](research/) | MENA and global analogue scan, market, buyers, economics | **No** | **No** |

---

## [`frontend/`](frontend/) — the build

Design language, validated tokens, data contracts, RTL architecture, and the phase plan for the
bilingual React + MapLibre interface.

Start at [`frontend/00-master-plan.md`](frontend/00-master-plan.md).

Task file: [`06-ali.md`](../../tasks/phase2/06-ali.md).

## [`research/`](research/) — the pitch

20 documents, ~36,400 words, 51 sources. Where else this problem happens, who would pay for solving
it, and what has actually been built.

Start at [`research/00-summary.md`](research/00-summary.md).

> **Not an app surface, and not in the RAG corpus.** It backs the market slide and answers *"is this
> only for Aqaba?"* in Q&A. Building it into the UI would spend frontend days on something one slide
> already covers — see [`06-ali.md`](../../tasks/phase2/06-ali.md) §One note on the research documents.
