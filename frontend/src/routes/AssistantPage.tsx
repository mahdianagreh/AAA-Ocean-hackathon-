import { useId, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { CaveatList } from '../components/CaveatList';
import {
  chatWithAssistant,
  type AssistantChatCaveat,
  type AssistantChatMessage,
  type AssistantToolCall,
  type Citation,
} from '../api/live';
import { matchRoute, navigate } from '../app/useRoute';
import { useUi } from '../app/uiStore';

/** Ask, at /assistant.
 *
 *  Rebuilt as a real tool-calling chat (gemma4:31b, via `POST /api/v1/assistant/chat`
 *  — see `backend/src/models/assistant_agent.py`). Earlier this page only quoted
 *  retrieved excerpts and had no LLM anywhere in its path; that is no longer true.
 *  A real model now writes the reply, and it can call tools to look up this
 *  system's own live data (an alert, a reef zone, a stored run) rather than only
 *  the technical docs. What has NOT changed: it still never invents or recomputes
 *  a number — every figure in an answer is checked against what a tool actually
 *  returned before this ever renders it, and an answer that fails that check
 *  carries a caveat rather than shipping silently. `t('assistant.honestFraming')`
 *  is that banner, shown once, plainly, not as a badge in a corner.
 *
 *  Conversation state is client-side only, same as every other stateless
 *  endpoint in this API — no server-side chat storage, capped history sent with
 *  each turn (`MAX_HISTORY_TURNS` on the backend). */

type Msg =
  | { key: number; role: 'user'; text: string }
  | {
      key: number;
      role: 'assistant';
      text: string;
      toolsUsed: AssistantToolCall[];
      citations: Citation[];
      suggestedRoute: string | null;
      caveats: AssistantChatCaveat[];
    }
  | { key: number; role: 'error'; text: string };

const SUGGESTION_KEYS = [
  'alerts',
  'guide',
  'satellite',
  'currents',
  'sensitivity',
  'catchments',
  'transmission',
  'market',
] as const;

function GoToRouteButton({ path }: { path: string }) {
  const { t } = useTranslation('tools');
  const routeName = matchRoute(path).name;
  const label = t(`nav:${routeName}`, { defaultValue: path });
  return (
    <button
      type="button"
      onClick={() => navigate(path)}
      className="inline-flex h-9 w-fit cursor-pointer items-center gap-1.5 rounded-full border-2 border-accent px-4 text-xs font-bold text-accent transition-colors hover:bg-accent/10"
    >
      {t('assistant.goToRoute', { label })}
    </button>
  );
}

function CitationCards({ citations }: { citations: Citation[] }) {
  const { t } = useTranslation('tools');
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-col gap-3 mt-2">
      <h4 className="m-0 text-xs font-bold premium-gradient-text">
        {t('assistant.citations', { n: citations.length })}
      </h4>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {citations.map((c, i) => (
          <li key={`${c.source_file}#${c.section}#${i}`} data-citation={i} className="flex gap-3 glass-panel p-4">
            <span
              aria-hidden="true"
              className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink text-2xs font-bold num text-ink-inverse"
            >
              {i + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <blockquote dir="auto" className="m-0 max-w-prose border-s-4 border-accent ps-3 text-xs text-ink-2">
                {c.excerpt}
              </blockquote>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-2xs text-ink-2">
                  <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num font-semibold">
                    {c.source_file}
                  </code>
                  <span dir="auto" className="opacity-70">§ {c.section}</span>
                </span>
                {c.score != null ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-2xs text-ink-2">
                    {t('assistant.scoreLabel')}{' '}
                    <span dir="ltr" className="num font-mono">{c.score.toFixed(2)}</span>
                  </span>
                ) : null}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ToolsUsedDisclosure({ tools }: { tools: AssistantToolCall[] }) {
  const { t } = useTranslation('tools');
  if (tools.length === 0) return null;
  return (
    <details className="glass-panel">
      <summary className="cursor-pointer p-3 text-2xs font-semibold text-accent list-none [&::-webkit-details-marker]:hidden">
        {t('assistant.toolsUsedToggle')}
      </summary>
      <ul className="m-0 flex list-none flex-col gap-1.5 px-3 pb-3">
        {tools.map((tc, i) => (
          <li key={i} className="text-2xs text-ink-2">
            <span className="font-semibold text-ink">
              {t(`assistant.tool.${tc.tool}`, { defaultValue: tc.tool })}:
            </span>{' '}
            {tc.summary}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function AssistantPage() {
  const { t } = useTranslation('tools');
  const lang = useUi((s) => s.lang);
  const inputId = useId();
  const keyRef = useRef(0);

  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [sending, setSending] = useState(false);

  function nextKey() {
    keyRef.current += 1;
    return keyRef.current;
  }

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const history: AssistantChatMessage[] = messages
      .filter((m): m is Msg & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, text: m.text }));

    setMessages((prev) => [...prev, { key: nextKey(), role: 'user', text: trimmed }]);
    setQuestion('');
    setSending(true);

    const res = await chatWithAssistant(trimmed, history, lang);

    setSending(false);
    if (!res) {
      setMessages((prev) => [...prev, { key: nextKey(), role: 'error', text: t('assistant.sendFailed') }]);
      return;
    }
    setMessages((prev) => [
      ...prev,
      {
        key: nextKey(),
        role: 'assistant',
        text: res.text,
        toolsUsed: res.tools_used,
        citations: res.citations,
        suggestedRoute: res.suggested_route,
        caveats: res.caveats,
      },
    ]);
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(question);
  };

  return (
    <PageShell title={t('assistant.title')} lede={t('assistant.lede')}>
      <Section label={t('assistant.title')}>
        <Card>
          <div className="flex items-start gap-2 rule bg-surface-2 p-3 text-2xs text-ink-2">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-px shrink-0 text-accent">
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 7.2v3.6" />
              <circle cx="8" cy="4.9" r="0.5" fill="currentColor" />
            </svg>
            <span className="max-w-prose">{t('assistant.honestFraming')}</span>
          </div>

          <div aria-live="polite" className="mx-auto flex w-full max-w-[46rem] flex-col gap-4 mt-4">
            {messages.map((m) => {
              if (m.role === 'user') {
                return (
                  <p key={m.key} dir="auto" className="m-0 ms-auto max-w-prose rounded-e-xl rounded-ss-xl bg-accent/10 px-4 py-2.5 text-sm text-ink">
                    {m.text}
                  </p>
                );
              }
              if (m.role === 'error') {
                return (
                  <p key={m.key} role="alert" className="m-0 text-xs text-risk-critical">
                    {m.text}
                  </p>
                );
              }
              return (
                <div key={m.key} className="flex flex-col gap-3">
                  <blockquote dir="auto" className="m-0 max-w-prose whitespace-pre-line border-s-4 border-accent bg-accent/5 p-5 rounded-e-xl text-sm leading-relaxed text-ink shadow-inner">
                    {m.text}
                  </blockquote>
                  {m.suggestedRoute ? <GoToRouteButton path={m.suggestedRoute} /> : null}
                  <ToolsUsedDisclosure tools={m.toolsUsed} />
                  <CitationCards citations={m.citations} />
                  <CaveatList items={m.caveats} title={t('assistant.caveatsLabel')} />
                </div>
              );
            })}
            {sending ? <p className="m-0 text-xs text-ink-3" aria-live="polite">{t('assistant.thinking')}</p> : null}
          </div>

          <form className="flex flex-col gap-3 mt-4" onSubmit={onSubmit}>
            <label htmlFor={inputId} className="text-xs font-semibold">
              {t('assistant.label')}
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <input
                id={inputId}
                type="search"
                dir="auto"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={t('assistant.placeholder')}
                data-assistant-input="true"
                className="h-12 flex-1 min-w-[16rem] rounded-full border border-hairline bg-surface/50 px-5 text-sm text-ink placeholder:text-ink-3 hover:border-accent focus:border-accent outline-none transition-colors shadow-inner"
              />
              <button
                type="submit"
                disabled={!question.trim() || sending}
                className="h-10 rounded-full px-6 text-sm font-bold premium-button hover:premium-button-hover disabled:opacity-50 cursor-pointer"
              >
                {sending ? t('assistant.thinking') : t('assistant.send')}
              </button>
            </div>
          </form>

          <div className="flex flex-col gap-2 mt-3">
            <p className="m-0 text-2xs text-ink-3">{t('assistant.tryThese')}</p>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {SUGGESTION_KEYS.map((k) => {
                const q = t(`assistant.suggestions.${k}`);
                return (
                  <li key={k}>
                    <button
                      type="button"
                      onClick={() => void send(q)}
                      disabled={sending}
                      className="glass-panel px-3 py-1.5 text-xs text-ink-2 hover:border-accent hover:text-accent transition-colors cursor-pointer shadow-none disabled:opacity-50"
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
    </PageShell>
  );
}
