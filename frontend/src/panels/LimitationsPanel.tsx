import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadLimitations, type Limitations } from '../api/panels';
import { useUi } from '../app/uiStore';

/** DoD item 6: the in-app limitations page.
 *
 *  Rendered from docs/pitch_limitations.md and docs/forcing_limitations.md rather
 *  than retyped, so the page cannot drift from the documents the team maintains —
 *  and a limitation fixed in the repo disappears from the UI on the next
 *  derivation rather than lingering as a stale warning.
 *
 *  06 §6 calls the Arabic here "the item with no technical fallback": machine
 *  translating scientific caveats is exactly what concept §22.4 scores against. So
 *  the body text stays in its source language and says so, while every heading and
 *  every framing sentence is translated and reviewed. That is the honest split
 *  until a human reviews the bodies — a machine-translated caveat that reads
 *  fluently is worse than an English one that is marked as English.
 */
export function LimitationsPanel() {
  const { t } = useTranslation();
  const lang = useUi((s) => s.lang);
  const [l, setL] = useState<Limitations | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadLimitations()
      .then((d) => live && setL(d))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;
  if (!l) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  return (
    <div className="flex flex-col gap-5" data-panel="limitations">
      {lang === 'ar' ? (
        // Stated, not hidden. A reader in Arabic is told why the detail below is
        // in English rather than being handed a fluent machine translation of a
        // scientific caveat.
        <p className="rule bg-surface-2 p-2 text-xs text-ink-2">{t('limitations.arabicPending')}</p>
      ) : null}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{t('limitations.oneLine')}</h3>
        <p dir="ltr" className="max-w-prose text-xs text-ink-2">
          {strip(l.one_line)}
        </p>
      </section>

      {/* The ~9 km ocean model. The same fact the map draws as the grid overlay, so
          the text and the honesty device agree instead of one contradicting the
          other. */}
      <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h3 className="text-sm font-semibold">{t('limitations.forcing')}</h3>
        <p dir="ltr" className="max-w-prose text-xs text-ink-2">
          {strip(l.forcing.statement)}
        </p>
        <p className="text-2xs text-ink-2">{t('limitations.forcingSeeGrid')}</p>
        <p className="text-2xs text-ink-2">
          <code className="font-mono num">{l.forcing.source}</code>
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold">
          {t('limitations.items', { n: l.items.length })}
        </h3>
        <ol className="flex flex-col gap-3">
          {l.items.map((it) => (
            <li key={it.n} data-limitation={it.n} className="flex flex-col gap-1">
              <h4 className="flex items-baseline gap-2 text-xs font-semibold">
                <span
                  dir="ltr"
                  style={{ unicodeBidi: 'isolate' }}
                  className="font-mono num text-2xs text-ink-3"
                >
                  {String(it.n).padStart(2, '0')}
                </span>
                <span dir="ltr">{strip(it.title)}</span>
              </h4>
              <p dir="ltr" className="max-w-prose text-2xs text-ink-2">
                {strip(it.body).slice(0, 700)}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <p className="text-2xs text-ink-3">
        {t('validation.source')}{' '}
        {l.sources.map((s) => (
          <code key={s} className="me-2 font-mono num">
            {s}
          </code>
        ))}
      </p>
    </div>
  );
}

/** Markdown emphasis and code fences are noise in a rendered panel. Deliberately
 *  not a markdown renderer: these bodies are prose with the occasional bold, and a
 *  parser would be a dependency plus an XSS surface for content we already own. */
function strip(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/[`*_>]/g, '')
    .replace(/\[(.+?)\]\((.+?)\)/g, '$1')
    .replace(/\n{2,}/g, '\n\n')
    .trim();
}
