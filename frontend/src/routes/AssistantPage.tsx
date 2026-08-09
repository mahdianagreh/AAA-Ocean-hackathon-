import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { ask, type AskResponse } from '../api/live';
import { useUi } from '../app/uiStore';

/** Ask, at /assistant.
 *
 *  BEHAVIOUR CHANGE, STATED RATHER THAN SLIPPED IN. The overlay panel
 *  (src/panels/Assistant.tsx) answers entirely client-side: it ships a fixture
 *  corpus, scores it with IDF-weighted keyword search in the browser, and never
 *  touches the network. That is still what the overlay does, and it is why the
 *  overlay keeps working with wifi off. THIS PAGE DOES NOT DO THAT. It calls
 *  POST /api/v1/ask and renders the backend's answer, so what a reader sees here
 *  is the retrieval the product actually ships, over the real corpus, and it can
 *  disagree with the offline panel.
 *
 *  There is no LLM anywhere in this path. The backend does lexical retrieval and
 *  composes the answer by quoting the sections it found — extractive, not
 *  generative. Nothing paraphrases, so nothing can drift from the source. Saying
 *  "AI answer" here would misdescribe it in the direction that loses the Q&A.
 *
 *  The citation rule is enforced at the render, not by a warning badge: an answer
 *  that comes back with an empty citation list is not rendered as an answer at
 *  all. The no-sourced-answer state replaces it and reports how many corpus files
 *  were searched, which is a true statement where a hedge would not be.
 */

type State =
  | { kind: 'idle' }
  | { kind: 'asking' }
  | { kind: 'answered'; response: AskResponse }
  | { kind: 'unsourced'; searched: number | null }
  | { kind: 'unreachable' };

/** Openers that exercise both states. The first four are answerable from the
 *  documentation; the last two are the corpus boundary — the market and business
 *  research is deliberately outside it, so those genuinely have no sourced
 *  answer, and demonstrating that is the point of including them. */
const SUGGESTION_KEYS = [
  'satellite',
  'currents',
  'sensitivity',
  'catchments',
  'transmission',
  'market',
] as const;

export function AssistantPage() {
  const { t } = useTranslation('tools');
  const lang = useUi((s) => s.lang);
  const inputId = useId();

  const [question, setQuestion] = useState('');
  const [asked, setAsked] = useState('');
  const [state, setState] = useState<State>({ kind: 'idle' });

  async function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setAsked(trimmed);
    setState({ kind: 'asking' });

    // Language is passed, not assumed: the backend answers in the language it is
    // asked in, and an Arabic reader getting an English answer would be a silent
    // downgrade rather than a visible one.
    const res = await ask(trimmed, lang, 5);

    if (!res) {
      setState({ kind: 'unreachable' });
      return;
    }
    if (!res.citations.length) {
      setState({ kind: 'unsourced', searched: res.corpus_files_searched ?? null });
      return;
    }
    setState({ kind: 'answered', response: res });
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void run(question);
  };

  return (
    <PageShell title={t('assistant.title')} lede={t('assistant.lede')}>
      <Section label={t('assistant.askSection')}>
        <Card>
          <form className="flex flex-col gap-3" onSubmit={onSubmit}>
            <label htmlFor={inputId} className="text-xs font-semibold">
              {t('assistant.label')}
            </label>
            <input
              id={inputId}
              type="search"
              dir="auto"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t('assistant.placeholder')}
              data-assistant-input="true"
              className="h-12 w-full rounded-full border border-hairline bg-surface/50 px-5 text-sm text-ink placeholder:text-ink-3 hover:border-accent focus:border-accent outline-none transition-colors shadow-inner"
            />
            <div className="flex flex-wrap items-center gap-3 mt-1">
              <button
                type="submit"
                disabled={!question.trim() || state.kind === 'asking'}
                className="h-10 rounded-full px-6 text-sm font-bold premium-button hover:premium-button-hover disabled:opacity-50 cursor-pointer"
              >
                {state.kind === 'asking' ? t('assistant.asking') : t('assistant.ask')}
              </button>
              <span className="text-2xs text-ink-3">{t('assistant.notGenerative')}</span>
            </div>
          </form>

          <div className="flex flex-col gap-2">
            <p className="m-0 text-2xs text-ink-3">{t('assistant.tryThese')}</p>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {SUGGESTION_KEYS.map((k) => {
                const q = t(`assistant.suggestions.${k}`);
                return (
                  <li key={k}>
                    <button
                      type="button"
                      onClick={() => {
                        setQuestion(q);
                        void run(q);
                      }}
                      className="glass-panel px-3 py-1.5 text-xs text-ink-2 hover:border-accent hover:text-accent transition-colors cursor-pointer shadow-none"
                    >
                      {q}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </Card>
      </Section>

      <Section label={t('assistant.answerSection')}>
        <div aria-live="polite" className="flex flex-col gap-4">
          {state.kind === 'idle' ? (
            <p className="m-0 text-xs text-ink-3">{t('assistant.idle')}</p>
          ) : null}

          {state.kind === 'asking' ? (
            <p className="m-0 text-xs text-ink-3">{t('assistant.asking')}</p>
          ) : null}

          {state.kind === 'unreachable' ? (
            <Card>
              <h3 className="m-0 text-sm font-semibold">{t('assistant.unreachableTitle')}</h3>
              <p className="m-0 max-w-prose text-xs text-ink-2">{t('assistant.unreachableBody')}</p>
            </Card>
          ) : null}

          {state.kind === 'unsourced' ? (
            // A different render, not a badge on an answer-shaped container.
            // There is no answer, so nothing here looks like one.
            <Card>
              <div data-assistant-state="no_sourced_answer" className="flex flex-col gap-2">
                <h3 className="m-0 text-sm font-semibold">{t('assistant.noAnswerTitle')}</h3>
                <p className="m-0 max-w-prose text-xs text-ink-2">{t('assistant.noAnswerBody')}</p>
                <p className="m-0 text-2xs text-ink-2">
                  {state.searched === null
                    ? t('assistant.searchedUnknown')
                    : t('assistant.searchedCount', { n: state.searched })}
                </p>
                <p className="m-0 max-w-prose text-2xs text-ink-3">
                  {t('assistant.corpusBoundary')}
                </p>
                <p className="m-0 text-2xs text-ink-3">
                  {t('assistant.questionWas')}{' '}
                  <span dir="auto" className="text-ink-2">
                    {asked}
                  </span>
                </p>
              </div>
            </Card>
          ) : null}

          {state.kind === 'answered' ? (
            <Card>
              <div data-assistant-state="answered" className="flex flex-col gap-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">{t('assistant.answerTitle')}</h3>
                  <span className="rounded-sm border border-hairline-2 bg-surface-2 px-1.5 py-0.5 text-2xs text-ink-2">
                    {t('assistant.extractive')}
                  </span>
                </div>

                {/* Marked as a quotation, because it is quotation: the backend
                    composes the answer out of the sections it retrieved. */}
                <blockquote
                  dir="auto"
                  className="m-0 max-w-prose whitespace-pre-line border-s-4 border-accent bg-accent/5 p-5 rounded-e-xl text-sm leading-relaxed text-ink shadow-inner"
                >
                  {state.response.answer}
                </blockquote>

                <div className="flex flex-col gap-3 mt-4">
                  <h4 className="m-0 text-xs font-bold premium-gradient-text">
                    {t('assistant.citations', { n: state.response.citations.length })}
                  </h4>
                  <ol className="m-0 flex list-none flex-col gap-3 p-0">
                    {state.response.citations.map((c, i) => (
                      <li
                        key={`${c.source_file}#${c.section}#${i}`}
                        data-citation={i}
                        className="flex flex-col gap-2 glass-panel p-4 transition-all duration-300 hover:glass-panel-hover border-s-4 border-hairline-2 hover:border-s-accent cursor-default group"
                      >
                        <span className="flex flex-wrap items-baseline gap-2 text-xs">
                          <code dir="ltr" className="font-mono num font-bold text-ink group-hover:text-accent transition-colors">
                            {c.source_file}
                          </code>
                          <span dir="auto" className="text-ink-3 font-semibold">
                            § {c.section}
                          </span>
                        </span>
                        <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
                          {c.excerpt}
                        </p>
                      </li>
                    ))}
                  </ol>
                </div>

                <p className="m-0 text-2xs text-ink-3">
                  {t('assistant.searchedCount', { n: state.response.corpus_files_searched })}
                  {' · '}
                  {t('assistant.answerLanguage', {
                    language: t(`assistant.language.${state.response.language}`),
                  })}
                </p>
              </div>
            </Card>
          ) : null}
        </div>
      </Section>
    </PageShell>
  );
}
