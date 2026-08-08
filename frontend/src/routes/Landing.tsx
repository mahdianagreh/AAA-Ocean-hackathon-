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
                  className="rounded-md border px-5 py-4"
                  style={{ background: BRAND_VEIL, borderColor: BRAND_VEIL_EDGE }}
                >
                  <span className="num block text-lg font-bold">
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
