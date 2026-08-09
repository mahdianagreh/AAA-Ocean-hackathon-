import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadLimitations, type Limitations } from '../api/panels';
import { useUi } from '../app/uiStore';
import { Link } from '../components/Link';

/** DoD item 6: the in-app limitations page — and the highest-impact honesty
 *  surface in the product.
 *
 *  Rendered from docs/pitch_limitations.md and docs/forcing_limitations.md rather
 *  than retyped, so the page cannot drift from the documents the team maintains.
 *
 *  06 §6 calls the Arabic here "the item with no technical fallback": machine
 *  translating scientific caveats is exactly what the concept scores against. So
 *  the body text stays in its source language and says so.
 *
 *  Phase 8: the numbered limitations are a keyboard-operable accordion (native
 *  <details>, so aria-expanded and Enter/Space come from the platform), each body
 *  is rendered IN FULL (no truncation), a jump-nav opens and scrolls to any item,
 *  and a deep link (#limitation-N) opens that item expanded. The one-line version
 *  is a lead callout; the ocean-model resolution is a spotlight with an actionable
 *  link to the map's grid layer. The source document carries more numbered
 *  sections than the derived fixture surfaces — that gap is stated, not hidden,
 *  and the four scoped-but-unbuilt B-features are named here because this is where
 *  absent things are named. */

const ABSENT_KEYS = ['b1', 'b2', 'b3', 'b9'] as const;

export function LimitationsPanel() {
  const { t } = useTranslation();
  const lang = useUi((s) => s.lang);
  const layers = useUi((s) => s.layers);
  const toggleLayer = useUi((s) => s.toggleLayer);
  const setOverlay = useUi((s) => s.setOverlay);
  const [l, setL] = useState<Limitations | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const detailsRefs = useRef<Map<number, HTMLDetailsElement>>(new Map());

  useEffect(() => {
    let live = true;
    void loadLimitations()
      .then((d) => live && setL(d))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  // Deep link: open + scroll the numbered item named in the hash.
  useEffect(() => {
    if (!l) return;
    const m = /#limitation-(\d+)/.exec(window.location.hash);
    if (!m) return;
    const el = detailsRefs.current.get(Number(m[1]));
    if (el) {
      el.open = true;
      el.scrollIntoView({ block: 'start' });
    }
  }, [l]);

  function jump(id: string, n?: number) {
    if (n != null) {
      const el = detailsRefs.current.get(n);
      if (el) el.open = true;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;
  if (!l) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  return (
    <div className="flex flex-col gap-6" data-panel="limitations">
      {lang === 'ar' ? (
        <p className="m-0 rule bg-surface-2 p-3 text-sm font-medium text-ink-2">
          {t('limitations.arabicPending')}
        </p>
      ) : null}

      {/* Lead callout — the one-line version, given real weight. */}
      <section
        id="lim-oneline"
        className="flex flex-col gap-2 rounded-card border-s-4 border-accent bg-surface-2 p-5"
      >
        <h3 className="m-0 text-2xs font-bold uppercase tracking-wide text-accent">
          {t('limitations.oneLine')}
        </h3>
        <p dir="ltr" className="m-0 max-w-prose text-lg font-semibold leading-relaxed text-ink">
          {strip(l.one_line)}
        </p>
      </section>

      {/* Jump navigation. Buttons (not anchors) so it works identically inside the
          scrollable overlay and the full page, and opens the accordion item. */}
      <nav aria-label={t('limitations.jumpTo')} className="flex flex-col gap-2 rule p-4">
        <h3 className="m-0 text-2xs font-bold uppercase tracking-wide text-ink-2">
          {t('limitations.jumpTo')}
        </h3>
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1.5 p-0">
          <li>
            <button type="button" onClick={() => jump('lim-forcing')} className="cursor-pointer text-2xs font-semibold text-accent hover:underline">
              {t('limitations.forcing')}
            </button>
          </li>
          {l.items.map((it) => (
            <li key={it.n}>
              <button
                type="button"
                onClick={() => jump(`limitation-${it.n}`, it.n)}
                className="cursor-pointer text-2xs font-semibold text-accent hover:underline"
              >
                <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num">{String(it.n).padStart(2, '0')}</span>{' '}
                {strip(it.title)}
              </button>
            </li>
          ))}
          <li>
            <button type="button" onClick={() => jump('lim-absent')} className="cursor-pointer text-2xs font-semibold text-accent hover:underline">
              {t('limitations.absentTitle')}
            </button>
          </li>
        </ul>
      </nav>

      {/* Ocean-model resolution, as a spotlight card with an actionable link that
          turns the map's grid layer ON and closes this panel — so it works both
          on /limitations (navigates to the map) and inside the map overlay (where
          a plain /dashboard link would be a same-path no-op). */}
      <section id="lim-forcing" className="flex flex-col gap-2 glass-panel p-5">
        <h3 className="m-0 text-md font-bold text-ink">{t('limitations.forcing')}</h3>
        <p dir="ltr" className="m-0 max-w-prose text-sm leading-relaxed text-ink-2">
          {strip(l.forcing.statement)}
        </p>
        <Link
          to="/dashboard"
          onNavigate={() => {
            if (!layers.modelGrid) toggleLayer('modelGrid');
            setOverlay(null);
          }}
          className="w-fit text-xs font-semibold text-accent hover:underline"
        >
          {t('limitations.forcingSeeGrid')}
        </Link>
        <p className="m-0 text-2xs text-ink-2">
          <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
            {l.forcing.source}
          </code>
        </p>
      </section>

      {/* The numbered limitations, as a keyboard-operable accordion. */}
      <section className="flex flex-col gap-3">
        <h3 className="m-0 text-lg font-bold premium-gradient-text">
          {t('limitations.items', { n: l.items.length })}
        </h3>
        <p className="m-0 text-2xs text-ink-3">{t('limitations.expandHint')}</p>
        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {l.items.map((it) => (
            <li key={it.n}>
              <details
                id={`limitation-${it.n}`}
                data-limitation={it.n}
                ref={(el) => {
                  if (el) detailsRefs.current.set(it.n, el);
                }}
                className="group glass-panel"
              >
                <summary className="flex cursor-pointer items-center gap-2 p-4 list-none [&::-webkit-details-marker]:hidden">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 text-ink-2 transition-transform group-open:rotate-90">
                    <path d="M6 4l4 4-4 4" />
                  </svg>
                  <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num text-xs font-bold text-accent">
                    {String(it.n).padStart(2, '0')}
                  </span>
                  <span dir="ltr" className="text-sm font-bold text-ink">{strip(it.title)}</span>
                </summary>
                <div className="px-4 pb-4 ps-8">
                  <p dir="ltr" className="m-0 max-w-prose whitespace-pre-line text-sm leading-relaxed text-ink-2">
                    {strip(it.body)}
                  </p>
                </div>
              </details>
            </li>
          ))}
        </ol>
        {/* The gap between the derived fixture and the source document, stated. */}
        <p className="m-0 max-w-prose text-2xs text-ink-3">{t('limitations.missingNote')}</p>
      </section>

      {/* Absent features — named on purpose (p4-13 / b1,b2,b3,b9). */}
      <section id="lim-absent" className="flex flex-col gap-3">
        <h3 className="m-0 text-md font-bold text-ink">{t('limitations.absentTitle')}</h3>
        <p className="m-0 max-w-prose text-xs text-ink-2">{t('limitations.absentIntro')}</p>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {ABSENT_KEYS.map((k) => (
            <li key={k} className="flex gap-2 glass-panel p-3">
              <span dir="ltr" className="num shrink-0 text-2xs font-bold text-ink-2">{k}</span>
              <span className="max-w-prose text-xs text-ink-2">{t(`limitations.absent.${k}`)}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="m-0 text-2xs text-ink-3">
        {t('validation.source')}{' '}
        {l.sources.map((s) => (
          <code key={s} dir="ltr" style={{ unicodeBidi: 'isolate' }} className="me-2 font-mono num">
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
