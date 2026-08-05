/** The honest panels' data, derived by scripts/15_frontend_panels.py.
 *
 *  Phase 3's gate is that every panel renders from real repo artefacts rather than
 *  mockups, so none of these shapes are invented — they mirror what the QA
 *  manifest, the limitation documents, the data dictionary and the event audit
 *  already contain.
 */

export interface Figure {
  file: string;
  caption: string;
  generated?: string;
  source?: string;
  thumb?: string;
  thumb_bytes?: number;
  full_bytes?: number;
  full_path?: string;
}

export interface Provenance {
  figures: Figure[];
  manifest_count: number;
  on_disk_count: number;
  /** The two later plume figures the manifest does not list. Driving the panel off
   *  the manifest silently omits them, which 07 §6 calls a decision not an
   *  accident — so the count is shown rather than the omission hidden. */
  omitted_from_manifest: string[];
  excluded: string[];
  excluded_reason_key: string;
}

export interface Limitations {
  one_line: string;
  items: Array<{ n: number; title: string; body: string }>;
  forcing: { statement: string; source: string };
  sources: string[];
}

export interface Validation {
  satellite: {
    verdict: string;
    heading: string;
    excerpt: string;
    source: string;
    /** Not a data-quality problem. The plume dispersed 2.5–3.5 days before any
     *  accessible pass, confirmed independently by Sentinel-2 and Landsat 8. No
     *  amount of searching fixes it, which is what makes it a finding. */
    is_physical_null: boolean;
  };
  mooring_target: {
    citation: string;
    doi: string;
    timing_utc: Record<string, unknown>;
    magnitude: Record<string, unknown>;
    position: Record<string, unknown>;
    calibration_use?: Record<string, unknown> | null;
  };
  /** null until a simulation run is registered. The panel shows the measured
   *  target against an explicit "not computed" rather than a fabricated match. */
  modelled: null | Record<string, unknown>;
  modelled_blocked_on: string;
}

export interface Sources {
  rows: string[][];
  source: string;
  share_alike_note_key: string;
}

export interface Corpus {
  chunks: Array<{ file: string; section: string; text: string }>;
  files: string[];
  excludes: string[];
  retrieval: string;
}

const url = (n: string) => `${import.meta.env.BASE_URL}fixtures/${n}.json`;

async function load<T>(name: string): Promise<T> {
  const r = await fetch(url(name));
  if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`);
  return (await r.json()) as T;
}

export const loadProvenance = () => load<Provenance>('provenance');
export const loadLimitations = () => load<Limitations>('limitations');
export const loadValidation = () => load<Validation>('validation');
export const loadSources = () => load<Sources>('sources');
export const loadCorpus = () => load<Corpus>('corpus');

// ---------------------------------------------------------------------------
// The assistant.
//
// 07 §4: "The union is the enforcement. `citations` is a non-empty tuple on the
// answered branch, so an uncited answer is unrepresentable rather than merely
// discouraged." That is the type below, and the retrieval underneath it is
// keyword search over real document sections — so a citation is always a real
// file and a real heading.
//
// Deliberately no generation. The assistant returns passages it found and says
// where they came from. Nothing paraphrases, so nothing can drift from the
// source, which is the failure mode concept §22.4 scores against.
// ---------------------------------------------------------------------------

export interface Citation {
  file: string;
  section: string;
  excerpt?: string;
}

export type AskResponse =
  | { status: 'answered'; text: string; citations: [Citation, ...Citation[]] }
  | { status: 'no_sourced_answer'; searched: string[] };

const STOP = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'is', 'are', 'was', 'were',
  'for', 'on', 'at', 'by', 'it', 'this', 'that', 'with', 'as', 'be', 'we',
  'what', 'how', 'why', 'when', 'where', 'does', 'do', 'did', 'can', 'our',
]);

const terms = (q: string) =>
  q
    .toLowerCase()
    .split(/[^a-z0-9؀-ۿ]+/)
    .filter((w) => w.length > 2 && !STOP.has(w));

/** Inverse document frequency, over the corpus itself.
 *
 *  This is the part that makes the corpus boundary real rather than declared.
 *  A flat term count let "what is our expected market value" score 4 against a
 *  section titled "Observed values in the smoke-test files" — "value" in the
 *  heading, "expected" in the body — and it would have rendered an ERA5 document
 *  as the answer to a market question, with a citation attached. That is exactly
 *  the overclaim 09 rule 3 forbids: not an uncited answer, but a cited wrong one,
 *  which is worse because the citation lends it credibility.
 *
 *  Weighting by rarity fixes it at the root. "value" and "expected" appear all
 *  over a technical corpus and carry almost nothing; "market" appears nowhere, so
 *  it contributes nothing to any chunk and the question falls below threshold.
 *  "satellite", "plume" and "transmission" are distinctive and score heavily.
 */
/** Word-boundary matching, not substring: `value` should not match inside an
 *  unrelated word, and the difference is measurable — `catchment` scores df 28 by
 *  substring against 25 by word. */
const boundary = (t: string) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`);

function docFreq(corpus: Corpus, term: string): number {
  const re = boundary(term);
  let df = 0;
  for (const c of corpus.chunks) {
    if (re.test(c.section.toLowerCase()) || re.test(c.text.toLowerCase())) df++;
  }
  return df;
}

function idfOf(corpus: Corpus, df: number): number {
  if (df === 0) return 0;
  return Math.log(corpus.chunks.length / df);
}

function score(
  chunk: Corpus['chunks'][number],
  ts: string[],
  weights: Map<string, number>,
): { s: number; matched: number } {
  const head = chunk.section.toLowerCase();
  const body = chunk.text.toLowerCase();
  let s = 0;
  let matched = 0;
  for (const t of ts) {
    const w = weights.get(t) ?? 0;
    const re = boundary(t);
    const inHead = re.test(head);
    const inBody = re.test(body);
    if (inHead || inBody) matched++;
    // A section whose *title* matches is far more likely to be the answer than one
    // that mentions the word once in passing.
    if (inHead) s += 3 * w;
    if (inBody) s += w;
  }
  return { s, matched };
}

export function ask(corpus: Corpus, question: string): AskResponse {
  const ts = terms(question);
  if (!ts.length) return { status: 'no_sourced_answer', searched: corpus.files };

  const dfs = new Map(ts.map((t) => [t, docFreq(corpus, t)]));

  /** THE CORPUS BOUNDARY, ENFORCED.
   *
   *  If any query term appears in zero sections, these documents do not cover that
   *  concept — and no ranking over the remaining words can honestly answer the
   *  question. "what is our expected market value" contains `market`, which appears
   *  nowhere; without this rule, `expected` and `value` alone ranked a SoilGrids
   *  section top and would have cited it. A cited wrong answer is worse than an
   *  uncited one, because the citation lends it authority.
   *
   *  This deliberately fails toward silence. A query with one unusual word gets
   *  "no sourced answer" plus the list of what was searched, which is a true
   *  statement — where answering the wrong document is not. Measured examples of
   *  terms genuinely absent from this corpus: `market`, and also `transmission` and
   *  `loss`, which confirms the correction the research already recorded against
   *  pitch_limitations.md: the infiltration problem is missing from it entirely. */
  const absent = ts.filter((t) => (dfs.get(t) ?? 0) === 0);
  if (absent.length) return { status: 'no_sourced_answer', searched: corpus.files };

  const weights = new Map(ts.map((t) => [t, idfOf(corpus, dfs.get(t) ?? 0)]));

  const hits = corpus.chunks
    .map((c) => ({ c, ...score(c, ts, weights) }))
    .filter(
      (h) =>
        // Two independent conditions, because each catches what the other misses.
        //
        // At least two distinct query terms must land: one word, however rare, is a
        // coincidence rather than a topic.
        h.matched >= 2 &&
        // And the match has to be on distinctive vocabulary. The threshold is in
        // IDF units, so it does not need retuning as the corpus grows.
        h.s >= 5,
    )
    .sort((a, b) => b.s - a.s)
    .slice(0, 3);

  if (!hits.length) {
    // A distinct render, not a hedge — and it shows what WAS searched, which 07 §4
    // calls more useful and more honest.
    return { status: 'no_sourced_answer', searched: corpus.files };
  }

  const citations = hits.map((h) => ({
    file: h.c.file,
    section: h.c.section,
    excerpt: h.c.text.slice(0, 420),
  })) as [Citation, ...Citation[]];

  return {
    status: 'answered',
    // The "answer" is the retrieved passage, verbatim. Not a summary of it.
    text: hits[0].c.text.slice(0, 700),
    citations,
  };
}
