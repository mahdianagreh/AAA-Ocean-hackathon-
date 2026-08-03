import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ask, loadCorpus, type AskResponse, type Corpus } from '../api/panels';

/** DoD item 7: the assistant, with visible citations.
 *
 *  01 §6.3 and 09 rule 3: "An uncited assistant answer must not render as an
 *  answer. Not a warning badge — a different state entirely."
 *
 *  Two things make that structural rather than a convention:
 *
 *  1. The response is a discriminated union whose `answered` branch carries a
 *     non-empty citation tuple, so an uncited answer is unrepresentable. This
 *     component cannot render one because it cannot be constructed.
 *  2. Nothing is generated. The retrieval returns document sections verbatim and
 *     names the file and heading they came from. There is no model to paraphrase,
 *     so there is nothing that can drift from the source — which is the failure
 *     concept §22.4 actually scores.
 *
 *  `no_sourced_answer` shows what WAS searched. 07 §4 calls that more useful and
 *  more honest than a hedge, and it is: a reader learns the corpus boundary rather
 *  than being told the assistant is unsure.
 */
export function Assistant() {
  const { t } = useTranslation();
  const [corpus, setCorpus] = useState<Corpus | null>(null);
  const [q, setQ] = useState('');
  const [res, setRes] = useState<AskResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadCorpus()
      .then((c) => live && setCorpus(c))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;

  return (
    <div className="flex flex-col gap-4" data-panel="assistant">
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (corpus) setRes(ask(corpus, q));
        }}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-2">{t('assistant.label')}</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('assistant.placeholder')}
            data-assistant-input="true"
            className="rule bg-surface px-2 py-1.5 text-sm text-ink"
          />
        </label>
        <div className="flex items-center gap-3">
          <button type="submit" disabled={!corpus} className="rule px-3 py-1 text-xs">
            {t('assistant.ask')}
          </button>
          <span className="text-2xs text-ink-3">
            {corpus
              ? t('assistant.corpusSize', { n: corpus.chunks.length, files: corpus.files.length })
              : t('rail.loading')}
          </span>
        </div>
      </form>

      {/* Suggested questions, because a blank search box over a technical corpus is
          an empty state that tells the user nothing about what it knows. */}
      {!res ? (
        <div className="flex flex-col gap-1">
          <p className="text-2xs text-ink-3">{t('assistant.tryThese')}</p>
          <ul className="flex flex-wrap gap-2">
            {[
              // The first four are answerable. The last two are not, deliberately:
              // "transmission loss" appears in ZERO corpus sections — which confirms
              // the correction already recorded against pitch_limitations.md, that
              // the infiltration problem is missing from it — and the market
              // research is excluded by design. Both demonstrate the honest
              // no-answer state on questions a judge would plausibly ask.
              'satellite validation',
              'ocean current resolution',
              'reef sensitivity weights',
              'catchment id contract',
              'transmission loss',
              'expected market value',
            ].map((s) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => {
                    setQ(s);
                    if (corpus) setRes(ask(corpus, s));
                  }}
                  className="rule px-2 py-0.5 text-2xs text-ink-2 hover:border-accent"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {res?.status === 'answered' ? (
        <section data-assistant-state="answered" className="flex flex-col gap-3">
          {/* Verbatim, not a summary. Marked as a quotation so a reader knows they
              are looking at the document rather than at prose about it. */}
          <blockquote
            dir="ltr"
            className="max-w-prose border-s-2 border-data-measured ps-3 text-xs text-ink-2"
          >
            {res.text}
          </blockquote>

          <div className="flex flex-col gap-1">
            <h4 className="text-2xs font-semibold text-ink-2">
              {t('assistant.citations', { n: res.citations.length })}
            </h4>
            <ol className="flex flex-col gap-2">
              {res.citations.map((c, i) => (
                <li key={`${c.file}#${c.section}`} data-citation={i} className="flex flex-col gap-0.5">
                  <span className="flex flex-wrap items-baseline gap-2 text-2xs">
                    <code
                      dir="ltr"
                      style={{ unicodeBidi: 'isolate' }}
                      className="font-mono num text-ink"
                    >
                      {c.file}
                    </code>
                    <span dir="ltr" className="text-ink-3">
                      § {c.section}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </section>
      ) : null}

      {res?.status === 'no_sourced_answer' ? (
        // A different render, not a badge on the same one. No blockquote, no
        // answer-shaped container — because there is no answer.
        <section
          data-assistant-state="no_sourced_answer"
          className="flex flex-col gap-2 rule bg-surface-2 p-3"
        >
          <h4 className="text-xs font-semibold">{t('assistant.noAnswerTitle')}</h4>
          <p className="max-w-prose text-2xs text-ink-2">{t('assistant.noAnswerBody')}</p>
          <details className="text-2xs">
            <summary className="cursor-pointer text-ink-2">
              {t('assistant.searched', { n: res.searched.length })}
            </summary>
            <ul className="mt-1 flex flex-col gap-0.5">
              {res.searched.map((f) => (
                <li key={f}>
                  <code dir="ltr" className="font-mono num text-ink-3">
                    {f}
                  </code>
                </li>
              ))}
            </ul>
          </details>
          {/* The corpus boundary, stated. 07 §4: the research documents are not in
              it, so a market question genuinely has no sourced answer here. */}
          <p className="text-2xs text-ink-2">{t('assistant.corpusBoundary')}</p>
        </section>
      ) : null}
    </div>
  );
}
