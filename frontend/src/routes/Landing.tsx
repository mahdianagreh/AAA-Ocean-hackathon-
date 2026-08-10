import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import {
  BRAND_VEIL,
  BRAND_VEIL_EDGE,
  GUTTER,
  MarketingFooter,
  MarketingNav,
  ON_BRAND,
  ON_BRAND_ACCENT,
  ON_BRAND_INK,
  ON_BRAND_SOFT,
} from '../shell/MarketingChrome';

/** The public marketing home, transcribed from the design canvas
 *  (`frontend/Foundation pages built/AQABA Foundation.dc.html`, the `isHome`
 *  block). Layout, order and copy are the design's; the palette is routed
 *  through the tokens, and the handful of values that sit on the fixed brand
 *  gradient come from the ON_BRAND_* constants in MarketingChrome, with the
 *  reason recorded there.
 *
 *  Two deliberate departures from the canvas, both because the canvas leaves a
 *  dangling link rather than because the design is wrong:
 *   - the nav's `#data-sources` anchor had no target section. It now points at
 *     the validation section, which is the one that talks about where the data
 *     comes from.
 *   - the footer's `href="#"` items point at the real routes that answer them.
 *
 *  All illustrative SVG is drawn in `currentColor` so it tracks the token on
 *  the element instead of freezing a brand hex into the page.
 */

const HERO_STATS = ['rainfall', 'sediment', 'reefZones', 'forecasting'] as const;

const CHAIN = ['rainfall', 'wadiFlow', 'seaEntry', 'reef'] as const;

const PILLARS = ['rainfall', 'runoff', 'sediment', 'plume', 'exposure'] as const;

const ASSURANCES = ['sensor', 'openData', 'limitations'] as const;

/** The wadi-to-reef chain, one glyph per link. Stroke only, `currentColor`. */
function ChainIcon({ step }: { step: (typeof CHAIN)[number] }) {
  const common = {
    width: 32,
    height: 32,
    viewBox: '0 0 32 32',
    fill: 'none',
    'aria-hidden': true,
    focusable: 'false',
  } as const;

  if (step === 'rainfall') {
    return (
      <svg {...common}>
        <path d="M4 26 L16 6 L28 26 Z" stroke="currentColor" strokeWidth="2" fill="none" />
      </svg>
    );
  }
  if (step === 'wadiFlow') {
    return (
      <svg {...common}>
        <path
          d="M4 10 L14 20 L20 14 L28 22"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    );
  }
  if (step === 'seaEntry') {
    return (
      <svg {...common}>
        <circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="2" fill="none" />
        <circle
          cx="16"
          cy="16"
          r="10"
          stroke="currentColor"
          strokeWidth="2"
          fill="none"
          opacity="0.5"
        />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M16 4 L28 28 L4 28 Z" stroke="currentColor" strokeWidth="2" fill="none" />
    </svg>
  );
}

/** One glyph per capability card. */
function PillarIcon({ pillar }: { pillar: (typeof PILLARS)[number] }) {
  const common = {
    width: 28,
    height: 28,
    viewBox: '0 0 28 28',
    fill: 'none',
    'aria-hidden': true,
    focusable: 'false',
  } as const;

  switch (pillar) {
    case 'rainfall':
      return (
        <svg {...common}>
          <circle cx="10" cy="10" r="6" stroke="currentColor" strokeWidth="2" fill="none" />
          <circle cx="17" cy="12" r="5" stroke="currentColor" strokeWidth="2" fill="none" />
          <line x1="9" y1="21" x2="9" y2="25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <line x1="16" y1="21" x2="16" y2="25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      );
    case 'runoff':
      return (
        <svg {...common}>
          <path
            d="M2 22 L11 8 L17 16 L26 4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
    case 'sediment':
      return (
        <svg {...common}>
          <circle cx="6" cy="20" r="2.5" fill="currentColor" />
          <circle cx="14" cy="14" r="2.5" fill="currentColor" />
          <circle cx="21" cy="21" r="2.5" fill="currentColor" />
          <circle cx="20" cy="9" r="2.5" fill="currentColor" />
        </svg>
      );
    case 'plume':
      return (
        <svg {...common}>
          <path
            d="M2 10 Q7 4 12 10 Q17 16 22 10 Q25 7 26 10"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M2 18 Q7 12 12 18 Q17 24 22 18 Q25 15 26 18"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
            opacity="0.5"
          />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M14 2 L24 14 L14 26 L4 14 Z" stroke="currentColor" strokeWidth="2" fill="none" />
        </svg>
      );
  }
}

export function Landing() {
  const { t } = useTranslation();

  return (
    <div className="bg-surface text-ink">
      <MarketingNav />

      <main>
        {/* ---- hero ------------------------------------------------------ */}
        <section
          className={`brand-gradient pt-[clamp(64px,10vw,128px)] pb-16 ${GUTTER}`}
          style={{ color: ON_BRAND }}
        >
          <div className="mx-auto flex max-w-[820px] flex-col items-center gap-6 text-center">
            <p
              className="m-0 text-xs font-bold tracking-[0.14em]"
              style={{ color: ON_BRAND_ACCENT }}
            >
              {t('landing.hero.eyebrow')}
            </p>
            <h1 className="m-0 text-[clamp(32px,6vw,64px)] leading-[1.08] font-bold">
              {t('landing.hero.title')}
            </h1>
            <p
              className="m-0 max-w-[620px] text-md leading-[1.6]"
              style={{ color: ON_BRAND_SOFT }}
            >
              {t('landing.hero.body')}
            </p>

            <div className="mt-2 flex flex-wrap justify-center gap-4">
              <Link
                to="/signup"
                className="flex h-12 items-center rounded-md px-7 text-sm font-bold"
                style={{ background: ON_BRAND, color: ON_BRAND_INK }}
              >
                {t('landing.hero.getAccess')}
              </Link>
              <a
                href="#how-it-works"
                className="flex h-12 items-center rounded-md border-[1.5px] px-7 text-sm font-semibold"
                style={{ borderColor: ON_BRAND, color: ON_BRAND }}
              >
                {t('landing.hero.seeHow')}
              </a>
            </div>

            <ul className="m-0 mt-8 grid w-full list-none grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-4 p-0 text-start">
              {HERO_STATS.map((k) => (
                <li
                  key={k}
                  className="rounded-md border px-5 py-4 transition-colors"
                  style={{ background: BRAND_VEIL, borderColor: BRAND_VEIL_EDGE }}
                >
                  <span className="num block text-xl font-bold leading-tight">
                    {t(`landing.hero.stats.${k}.value`)}
                  </span>
                  <span className="block text-xs" style={{ color: ON_BRAND_SOFT }}>
                    {t(`landing.hero.stats.${k}.label`)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ---- the problem, and the chain -------------------------------- */}
        <section className={`bg-surface py-24 ${GUTTER}`}>
          <div className="mx-auto grid max-w-[1200px] grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-center gap-12">
            <div className="flex flex-col gap-5">
              <h2 className="m-0 text-[clamp(24px,4vw,36px)] leading-[1.2] font-bold">
                {t('landing.problem.title')}
              </h2>
              <p className="m-0 text-sm leading-[1.7] text-ink-2">{t('landing.problem.body')}</p>
            </div>

            <ol
              aria-label={t('landing.problem.chainLabel')}
              className="m-0 flex list-none flex-wrap items-center justify-center gap-0 rounded-card bg-canvas p-8"
            >
              {CHAIN.map((step, i) => (
                <li key={step} className="flex items-center">
                  <span
                    className={`flex w-21 flex-col items-center gap-2 ${
                      i >= 2 ? 'text-accent' : 'text-ink'
                    }`}
                  >
                    <ChainIcon step={step} />
                    <span className="text-center text-xs text-ink-2">
                      {t(`landing.problem.chain.${step}`)}
                    </span>
                  </span>
                  {i < CHAIN.length - 1 ? (
                    <span aria-hidden="true" className="brand-gradient block h-0.5 w-7" />
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---- how it works ---------------------------------------------- */}
        <section id="how-it-works" className={`bg-surface-2 py-24 ${GUTTER}`}>
          <div className="mx-auto flex max-w-[1200px] flex-col gap-12">
            <h2 className="m-0 text-center text-[clamp(24px,4vw,36px)] font-bold">
              {t('landing.how.title')}
            </h2>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-6">
              {PILLARS.map((pillar) => (
                <article
                  key={pillar}
                  className="flex flex-col gap-3 rounded-card border border-hairline bg-surface p-6 shadow-sm"
                >
                  <span className={pillar === 'plume' ? 'text-accent' : 'text-ink'}>
                    <PillarIcon pillar={pillar} />
                  </span>
                  <h3 className="m-0 text-sm font-semibold">
                    {t(`landing.how.${pillar}.title`)}
                  </h3>
                  <p className="m-0 text-xs leading-[1.5] text-ink-2">
                    {t(`landing.how.${pillar}.body`)}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---- validation / where the data comes from --------------------- */}
        <section id="data-sources" className={`bg-surface py-24 ${GUTTER}`}>
          <div className="mx-auto flex max-w-[1200px] flex-col gap-10">
            <h2 className="m-0 text-center text-[clamp(24px,4vw,36px)] font-bold">
              {t('landing.validation.title')}
            </h2>
            <div className="flex flex-wrap items-center justify-between gap-8 rounded-card border border-hairline bg-surface p-[clamp(24px,4vw,48px)] shadow-sm">
              <p className="m-0 min-w-[280px] flex-[2] text-md leading-[1.5] font-semibold">
                {t('landing.validation.claim')}
              </p>
              <ul className="m-0 flex min-w-[240px] flex-1 list-none flex-col gap-3 p-0">
                {ASSURANCES.map((a) => (
                  <li key={a} className="flex items-center gap-3 text-xs text-ink-2">
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 18 18"
                      fill="none"
                      aria-hidden="true"
                      focusable="false"
                      className="shrink-0 text-accent"
                    >
                      <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="2" fill="none" />
                    </svg>
                    {t(`landing.validation.${a}`)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---- The Platform Preview (Bento Grid) -------------------------------- */}
        <section className={`bg-surface-2 py-24 ${GUTTER}`}>
          <div className="mx-auto flex max-w-[1200px] flex-col gap-16">
            <div className="text-center">
              <h2 className="m-0 text-[clamp(28px,5vw,48px)] font-bold tracking-tight">
                {t('landing.bento.title')}
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Backtesting - Large Span */}
              <div className="md:col-span-2 rounded-2xl overflow-hidden glass-panel border border-hairline p-8 flex flex-col md:flex-row gap-8 relative group hover:border-accent/50 transition-colors">
                <div className="flex-1 flex flex-col gap-4 z-10">
                  <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center text-accent shrink-0">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  </div>
                  <h3 className="m-0 text-2xl font-bold">{t('landing.bento.backtests.title')}</h3>
                  <p className="m-0 text-ink-2 leading-relaxed">{t('landing.bento.backtests.body')}</p>
                </div>
                <div className="flex-1 relative min-h-[150px] rounded-lg border border-hairline bg-surface-2/50 overflow-hidden shadow-inner flex items-center justify-center">
                   <div className="absolute inset-0 opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--brand-aqua)_0%,_transparent_70%)]" />
                   <div className="flex flex-col gap-2 w-3/4 z-10">
                     <div className="h-2 bg-accent rounded-full w-full opacity-80" />
                     <div className="h-2 bg-ink-3 rounded-full w-2/3 opacity-50" />
                     <div className="h-2 bg-ink-3 rounded-full w-4/5 opacity-50" />
                   </div>
                </div>
              </div>

              {/* System Health */}
              <div className="rounded-2xl glass-panel border border-hairline p-8 flex flex-col gap-4 group hover:border-accent/50 transition-colors">
                <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>
                </div>
                <h3 className="m-0 text-xl font-bold">{t('landing.bento.system.title')}</h3>
                <p className="m-0 text-ink-2 text-sm leading-relaxed">{t('landing.bento.system.body')}</p>
                <div className="mt-auto pt-6 flex justify-between items-end">
                  <div className="flex gap-1 items-end">
                    <div className="w-2 h-8 bg-ink-3 rounded-sm group-hover:bg-blue-400/50 transition-colors" />
                    <div className="w-2 h-12 bg-ink-3 rounded-sm group-hover:bg-blue-400/70 transition-colors" />
                    <div className="w-2 h-10 bg-ink-3 rounded-sm group-hover:bg-blue-400 transition-colors" />
                  </div>
                  <span className="text-2xs font-bold uppercase tracking-widest text-blue-400">OK</span>
                </div>
              </div>

              {/* Data Explorer */}
              <div className="md:col-span-3 rounded-2xl glass-panel border border-hairline p-8 flex flex-col md:flex-row-reverse gap-8 group hover:border-accent/50 transition-colors">
                 <div className="flex-1 flex flex-col gap-4 justify-center">
                  <div className="w-12 h-12 rounded-full bg-teal-500/20 flex items-center justify-center text-teal-400 shrink-0">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>
                  </div>
                  <h3 className="m-0 text-2xl font-bold">{t('landing.bento.explorer.title')}</h3>
                  <p className="m-0 text-ink-2 leading-relaxed">{t('landing.bento.explorer.body')}</p>
                </div>
                <div className="flex-[2] relative rounded-lg border border-hairline bg-canvas overflow-hidden flex flex-col sm:flex-row items-stretch sm:items-center p-6 gap-4">
                   <div className="w-full sm:w-1/3 h-full rounded bg-surface border border-hairline p-4 flex flex-col gap-3 opacity-80 group-hover:opacity-100 transition-opacity">
                     <div className="h-2 w-1/2 bg-ink-3 rounded" />
                     <div className="h-2 w-3/4 bg-ink-3 rounded" />
                     <div className="h-2 w-full bg-ink-3 rounded" />
                   </div>
                   <div className="w-full sm:w-2/3 h-full rounded bg-surface border border-hairline p-4 flex flex-col justify-center gap-3 opacity-80 group-hover:opacity-100 transition-opacity">
                     <div className="flex justify-between border-b border-hairline pb-2"><div className="h-2 w-8 bg-teal-400 rounded" /><div className="h-2 w-16 bg-teal-400/50 rounded" /></div>
                     <div className="flex justify-between"><div className="h-2 w-12 bg-ink-2 rounded" /><div className="h-2 w-24 bg-ink-3 rounded" /></div>
                     <div className="flex justify-between"><div className="h-2 w-10 bg-ink-2 rounded" /><div className="h-2 w-20 bg-ink-3 rounded" /></div>
                   </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---- Feature Spotlight -------------------------------- */}
        <section className={`bg-surface py-32 overflow-hidden ${GUTTER}`}>
          <div className="mx-auto flex max-w-[1200px] flex-col gap-32">
            
            {/* Spotlight 1 */}
            <div className="flex flex-col md:flex-row items-center gap-16 relative">
              <div className="flex-1 flex flex-col gap-6 z-10">
                <p className="m-0 text-xs font-bold tracking-[0.2em] text-accent">
                  {t('landing.spotlight.precision.eyebrow')}
                </p>
                <h2 className="m-0 text-[clamp(28px,4vw,40px)] font-bold leading-[1.1]">
                  {t('landing.spotlight.precision.title')}
                </h2>
                <p className="m-0 text-md text-ink-2 leading-[1.6]">
                  {t('landing.spotlight.precision.body')}
                </p>
              </div>
              <div className="flex-1 relative w-full h-[300px] md:h-[400px]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--brand-aqua)_0%,_transparent_60%)] opacity-20 blur-3xl rounded-full" />
                <div className="absolute inset-4 border border-accent/20 rounded-2xl glass-panel flex items-center justify-center overflow-hidden">
                  <div className="w-full h-full opacity-30 border-[0.5px] border-accent/10" style={{ backgroundImage: 'linear-gradient(var(--brand-aqua) 1px, transparent 1px), linear-gradient(90deg, var(--brand-aqua) 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
                  <svg className="absolute text-accent drop-shadow-[0_0_15px_var(--brand-aqua)]" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg>
                </div>
              </div>
            </div>

            {/* Spotlight 2 */}
            <div className="flex flex-col md:flex-row-reverse items-center gap-16 relative">
              <div className="flex-1 flex flex-col gap-6 z-10">
                <p className="m-0 text-xs font-bold tracking-[0.2em] text-accent">
                  {t('landing.spotlight.intelligence.eyebrow')}
                </p>
                <h2 className="m-0 text-[clamp(28px,4vw,40px)] font-bold leading-[1.1]">
                  {t('landing.spotlight.intelligence.title')}
                </h2>
                <p className="m-0 text-md text-ink-2 leading-[1.6]">
                  {t('landing.spotlight.intelligence.body')}
                </p>
              </div>
              <div className="flex-1 relative w-full h-[300px] md:h-[400px]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_#3fa7c9_0%,_transparent_60%)] opacity-20 blur-3xl rounded-full" />
                <div className="absolute inset-4 border border-[#3fa7c9]/20 rounded-2xl glass-panel flex items-center justify-center overflow-hidden p-8 flex-col gap-6">
                  <div className="w-full flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-[#3fa7c9]/30 flex-shrink-0 animate-pulse" />
                    <div className="h-4 bg-[#3fa7c9]/20 rounded-full w-full" />
                  </div>
                  <div className="w-full flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-red-500/30 flex-shrink-0 shadow-[0_0_20px_rgb(239,68,68)]" />
                    <div className="h-4 bg-red-500/20 rounded-full w-3/4" />
                  </div>
                  <div className="w-full flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-[#3fa7c9]/30 flex-shrink-0 animate-pulse" />
                    <div className="h-4 bg-[#3fa7c9]/20 rounded-full w-5/6" />
                  </div>
                </div>
              </div>
            </div>

          </div>
        </section>

        {/* ---- Trusted By Marquee -------------------------------- */}
        <section className={`bg-canvas py-16 border-y border-hairline ${GUTTER}`}>
          <div className="mx-auto flex flex-col items-center gap-10 max-w-[1200px] overflow-hidden">
            <p className="m-0 text-sm font-semibold tracking-widest text-ink-3 uppercase text-center">
              {t('landing.trusted.title')}
            </p>
            <div className="flex flex-wrap justify-center items-center gap-x-16 gap-y-10 opacity-40 grayscale hover:opacity-70 hover:grayscale-0 transition-all duration-500">
              <svg width="120" height="40" viewBox="0 0 120 40" fill="currentColor"><path d="M20 10 L30 30 L10 30 Z" /><rect x="40" y="15" width="60" height="10" /></svg>
              <svg width="140" height="40" viewBox="0 0 140 40" fill="currentColor"><circle cx="20" cy="20" r="10" /><path d="M40 20 Q 70 0 100 20 T 140 20" stroke="currentColor" strokeWidth="4" fill="none" /></svg>
              <svg width="110" height="40" viewBox="0 0 110 40" fill="currentColor"><rect x="10" y="10" width="20" height="20" rx="4" /><rect x="40" y="15" width="60" height="10" rx="2" /></svg>
              <svg width="130" height="40" viewBox="0 0 130 40" fill="currentColor"><path d="M10 20 L30 10 L50 20 L30 30 Z" /><rect x="60" y="15" width="60" height="10" /></svg>
            </div>
          </div>
        </section>

        {/* ---- why this reef: the sourced coral fact (p4-18) ------------- */}
        <section className={`bg-surface-2 py-24 ${GUTTER}`}>
          <div className="mx-auto flex max-w-[820px] flex-col items-center gap-5 text-center">
            <p className="m-0 text-xs font-bold tracking-[0.14em] text-accent">
              {t('landing.coralFact.eyebrow')}
            </p>
            <h2 className="m-0 text-[clamp(24px,4vw,36px)] leading-[1.2] font-bold">
              {t('landing.coralFact.title')}
            </h2>
            <p className="m-0 max-w-[680px] text-md leading-[1.6] text-ink-2">
              {t('landing.coralFact.fact')}
            </p>
            {/* The citation binds to the sourced fact above it, not to the
                product "turn" below — per p4-18: sourced, not folklore. The
                reference is Latin bibliographic text, so it stays dir=ltr and is
                not translated; only the "Source" label flips. */}
            <p className="m-0 inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-hairline bg-surface px-4 py-2 text-2xs text-ink-3">
              <span className="font-bold uppercase tracking-wide">
                {t('landing.coralFact.sourceLabel')}
              </span>
              <span dir="ltr">{t('landing.coralFact.source')}</span>
            </p>
            <p className="m-0 mt-2 max-w-[680px] text-sm leading-[1.6] text-ink-2">
              {t('landing.coralFact.turn')}
            </p>
          </div>
        </section>

        {/* ---- closing call to action ------------------------------------ */}
        <section
          className={`brand-gradient py-20 text-center ${GUTTER}`}
          style={{ color: ON_BRAND }}
        >
          <div className="mx-auto flex max-w-[680px] flex-col items-center gap-5">
            <h2 className="m-0 text-[clamp(24px,4vw,36px)] font-bold">{t('landing.cta.title')}</h2>
            <p className="m-0 text-sm" style={{ color: ON_BRAND_SOFT }}>
              {t('landing.cta.body')}
            </p>
            <Link
              to="/signup"
              className="mt-2 flex h-13 items-center rounded-md px-8 text-sm font-bold"
              style={{ background: ON_BRAND, color: ON_BRAND_INK }}
            >
              {t('landing.cta.button')}
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
