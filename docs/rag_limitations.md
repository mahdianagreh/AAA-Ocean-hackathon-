# What `/ask` can and cannot do

**ReefShield Aqaba · the retrieval layer over the project's own documentation**

`/ask` answers questions about this project by quoting its own documents and citing
them. It is deliberately narrow, and the narrowness is the feature — but a judge
should know exactly where the edges are.

---

## 1. It quotes. It does not summarise, and it does not reason.

There is **no generative model in the default path.** Answers are assembled from
the retrieved excerpts verbatim, with the source file and section beside each one.

That means:

- Every figure in an answer traces to a document, character for character. You can
  open the file and find it.
- It cannot synthesise across two documents into a new claim, because synthesising
  is exactly where a paraphrased number would come from.
- Long answers read like quotations, because they are quotations.

An LLM hook exists (`generate_with_llm`) and is **not wired**. If it is ever
enabled, the number-fidelity test must apply to it too.

---

## 2. Retrieval is lexical, so wording matters

Scoring is BM25 over locally-computed term statistics. No embedding service, no
API key, no network. It is deterministic: the same question returns the same
citations on the demo laptop, offline, every time.

The honest cost: **lexical retrieval misses paraphrase.** "How sure are you about
catchment size" does not share vocabulary with "area uncertainty". A hand-written
synonym map bridges the terms this corpus actually uses, which is a maintained
list, not a general solution. A question phrased in vocabulary nobody anticipated
may be refused even though the answer is in the corpus.

---

## 3. Two gates, and why the second one exists

An answer is returned only if a chunk clears **both**:

1. a BM25 score floor, and
2. a **term-coverage floor** — the chunk must cover at least 40% of the question's
   content terms.

The second gate was added after a real failure. Asked "what is the airspeed
velocity of an unladen swallow", the system returned a properly-cited chunk about
**ocean current velocity**. The citation was genuine; the answer was not
responsive. A score floor alone cannot tell those apart, because one uncommon term
matching strongly can carry a chunk over the line.

Consequence: a question whose real answer is expressed in mostly different words
than the question uses may be refused. We prefer that to a confident irrelevance.

---

## 4. The corpus is English. Arabic answers describe English sources.

Every document in the corpus is written in English. Arabic questions are handled by
mapping Arabic query terms onto the English vocabulary of the corpus, so retrieval
works — but **the citation, and therefore the quoted text, is English.**

So:
- `/explain` is genuinely bilingual. Its Arabic output is Arabic prose, and the
  numbers are identical to the English output by test.
- `/ask` in Arabic finds the right English document and quotes it. It does not
  translate the quotation, because translating a quoted limitation is how a
  limitation gets softened.

The Arabic term bridge is a curated list. An Arabic question using terms outside it
will be refused.

---

## 5. What is deliberately NOT in the corpus

`docs/ali/*` — the MENA and global analogue research — is **excluded**. It is
market and pitch material: it backs the market slide and the "is this only for
Aqaba?" answer in Q&A. It is not a technical app surface, and an answer to a data
question citing a market-sizing document would actively mislead.

The exclusion is enforced twice: the corpus is an explicit file allowlist, never a
glob, and `resolve()` independently refuses any path under an excluded directory.
`tests/test_ask_citations.py` asserts no indexed chunk comes from `docs/ali/`, and
also asserts that `docs/ali/` is non-empty — so the exclusion test cannot pass
trivially.

`docs/schema_proposals/*` is excluded for the same reason: a proposal is not a
decision, and quoting one as project fact would misrepresent the schema.

---

## 6. What it refuses

- Anything not in the corpus. The response is *"I don't have documented information
  to answer that"*, in the language asked, with an empty citation list.
- An answer it cannot cite. This is enforced by an assertion in the request path,
  not left to convention.

**An uncited answer is not shippable.** If retrieval finds nothing, the honest
refusal is the answer.

---

## 7. Corpus contents

13 files configured, 12 present. `docs/model_card.md` is listed and not yet
written; `resolve()` reports it as missing rather than silently shrinking the
corpus, because a corpus that quietly loses a file starts refusing questions it
used to answer.

Current index: **223 chunks across 12 files**, ~6,400 term vocabulary. Chunks
follow markdown section boundaries so a citation's `section` is a real heading a
reader can navigate to; the PDF is chunked by page.
