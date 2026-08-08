import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { Logo, LogoMark } from '../components/Logo';

/** The marketing shell — sticky nav and footer, shared by the public pages.
 *
 *  Extracted from the design canvas rather than inlined into Landing for the
 *  same reason the logo is one component: the nav is the only thing a visitor
 *  sees on every public screen, and two copies drift.
 *
 *  On colour: everything that sits on a normal ground goes through the tokens.
 *  The exceptions are the ON_BRAND_* constants below, each marked `token-ok`,
 *  exactly as components/Logo.tsx marks the trademark palette — see the note
 *  on the constant for why a token would be wrong there specifically.
 */

/** Type and slabs that sit ON the fixed brand artwork.
 *
 *  `--brand-gradient` is declared once in theme.css as a literal and does NOT
 *  invert for dark theme, because it is fixed brand artwork. Anything drawn on
 *  top of it therefore cannot track a token either: `--ink-inverse` resolves to
 *  navy under dark theme, which would put navy type on a navy gradient. The
 *  footer slab is the same case — a fixed dark brand ground, not a surface.
 *
 *  These are the brand sheet's own values. They are not a second palette and
 *  nothing outside the marketing pages may reference them.
 *
 *  Exported one at a time rather than as a single object because
 *  react/only-export-components allows a constant export and an object literal
 *  does not count as one — a bundled palette object costs the whole file its
 *  fast refresh. */

/** Type on the gradient. */
export const ON_BRAND = '#FFFFFF'; // token-ok: fixed brand artwork, must not track the theme
/** Secondary type on the gradient — brand "Pale Aqua". */
export const ON_BRAND_SOFT = '#E6F7FA'; // token-ok: fixed brand artwork, must not track the theme
/** Accent type on the gradient — brand "Aqua". */
export const ON_BRAND_ACCENT = '#00B7C3'; // token-ok: fixed brand artwork, must not track the theme
/** Type on a white button sitting on the gradient — brand "Deep Navy". */
export const ON_BRAND_INK = '#0A1F4D'; // token-ok: fixed brand artwork, must not track the theme
/** Translucent card on the gradient. No blur: 01 §3 rejects the glass look. */
export const BRAND_VEIL = 'rgb(255 255 255 / 0.12)';
export const BRAND_VEIL_EDGE = 'rgb(255 255 255 / 0.28)';

/** The footer slab and its furniture — local, nothing else draws on it. */
const FOOTER_GROUND = '#09111F'; // token-ok: fixed brand artwork, must not track the theme
const FOOTER_RULE = 'rgb(255 255 255 / 0.22)';
const FOOTER_INK_MUTED = 'rgb(230 247 250 / 0.62)';

/** Horizontal gutter from the design canvas, kept as its clamp so the marketing
 *  pages breathe the way they were drawn. */
export const GUTTER = 'px-[clamp(20px,5vw,48px)]';

/** `window.scrollY > 8` — the design's own threshold. The nav gains a shadow
 *  once the page has moved under it and loses it at the top, so the hero reads
 *  as continuous with the bar until it isn't. */
function useNavScrolled(): boolean {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return scrolled;
}

const NAV_LINK =
  'py-2 text-sm font-semibold text-ink hover:text-accent';

export function MarketingNav() {
  const { t } = useTranslation();
  const scrolled = useNavScrolled();

  return (
    <nav
      aria-label={t('landing.nav.label')}
      className={`sticky top-0 z-50 bg-surface transition-shadow ${
        scrolled ? 'shadow-sm' : ''
      }`}
    >
      <div
        className={`mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4 py-4 ${GUTTER}`}
      >
        <Link to="/" aria-label={t('landing.nav.home')} className="flex items-center">
          <Logo size={30} variant="gradient" />
        </Link>

        <div className="flex flex-wrap items-center gap-3 md:gap-[clamp(12px,2vw,28px)]">
          <a href="#how-it-works" className={NAV_LINK}>
            {t('landing.nav.howItWorks')}
          </a>
          <a href="#data-sources" className={NAV_LINK}>
            {t('landing.nav.dataSources')}
          </a>
          <Link to="/dashboard" className={NAV_LINK}>
            {t('landing.nav.platformPreview')}
          </Link>
          <Link
            to="/login"
            className="flex h-10 items-center rounded-md border-[1.5px] border-ink px-4 text-sm font-semibold text-ink hover:border-accent hover:text-accent"
          >
            {t('landing.nav.login')}
          </Link>
          <Link
            to="/signup"
            className="brand-gradient flex h-10 items-center rounded-md px-5 text-sm font-semibold shadow-sm"
            style={{ color: ON_BRAND }}
          >
            {t('landing.nav.getAccess')}
          </Link>
        </div>
      </div>
    </nav>
  );
}

/** The gradient panel beside the auth forms, from the canvas's `isLogin` /
 *  `isSignup` blocks. Hidden below the design's ~860px breakpoint, where the
 *  form takes the full width; `md:` is the nearest standard stop.
 *
 *  It is decoration plus two figures, so it is an <aside>: a screen reader
 *  reaching the form does not have to walk the marketing copy first. */
export function AuthAside({
  headline,
  stats,
  foot,
  waveFirst,
}: {
  headline: string;
  stats: ReadonlyArray<{ value: string; label: string }>;
  foot: string;
  /** The canvas stacks the illustration's layers in the opposite order on
   *  signup — waves behind the peaks rather than in front. */
  waveFirst?: boolean;
}) {
  const waves = (
    <>
      <path
        d="M4 78 Q22 64 40 78 Q58 92 76 78 Q94 64 116 78"
        stroke={ON_BRAND_ACCENT}
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M4 62 Q22 48 40 62 Q58 76 76 62 Q94 48 116 62"
        stroke={ON_BRAND}
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0.4"
      />
    </>
  );
  const peaks = (
    <>
      <path
        d="M20 40 L40 4 L60 40 Z"
        stroke={ON_BRAND}
        strokeWidth="2"
        fill="none"
        opacity="0.55"
      />
      <path
        d="M55 46 L75 18 L95 46 Z"
        stroke={ON_BRAND}
        strokeWidth="2"
        fill="none"
        opacity="0.35"
      />
    </>
  );

  return (
    <aside
      className="brand-gradient hidden min-w-[340px] flex-1 flex-col justify-between px-12 py-14 md:flex"
      style={{ color: ON_BRAND }}
    >
      <Link to="/" className="flex items-center gap-3">
        <LogoMark size={27} variant="white" />
        <span dir="ltr" className="text-sm font-bold tracking-[0.06em]">
          AQABA AQUA AI
        </span>
      </Link>

      <div className="flex max-w-[380px] flex-col gap-5">
        <svg
          width="120"
          height="90"
          viewBox="0 0 120 90"
          fill="none"
          aria-hidden="true"
          focusable="false"
          style={{ opacity: 0.9 }}
        >
          {waveFirst ? peaks : waves}
          {waveFirst ? waves : peaks}
        </svg>

        <p className="m-0 text-lg leading-[1.35] font-bold">{headline}</p>

        <ul className="m-0 flex list-none flex-wrap gap-6 p-0">
          {stats.map((s) => (
            <li key={s.label}>
              <span className="num block text-lg font-bold" style={{ color: ON_BRAND_ACCENT }}>
                {s.value}
              </span>
              <span className="block text-xs" style={{ color: ON_BRAND_SOFT }}>
                {s.label}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <p className="m-0 text-xs" style={{ color: ON_BRAND_SOFT, opacity: 0.85 }}>
        {foot}
      </p>
    </aside>
  );
}

function FooterColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <h2
        className="text-xs font-bold tracking-[0.08em]"
        style={{ color: ON_BRAND }}
      >
        {title}
      </h2>
      {children}
    </div>
  );
}

export function MarketingFooter() {
  const { t } = useTranslation();
  const link = 'py-1 text-sm hover:underline';

  return (
    <footer
      className={`pt-16 pb-8 ${GUTTER}`}
      style={{ background: FOOTER_GROUND, color: ON_BRAND_SOFT }}
    >
      <div className="mx-auto grid max-w-[1200px] grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-12">
        <div className="flex items-center gap-3">
          <LogoMark size={27} variant="white" />
          {/* dir="ltr" — the wordmark is a Latin trademark and must not reorder
              under <html dir="rtl">. Same rule as components/Logo.tsx. */}
          <span
            dir="ltr"
            className="text-sm font-bold tracking-[0.06em]"
            style={{ color: ON_BRAND }}
          >
            AQABA AQUA AI
          </span>
        </div>

        <FooterColumn title={t('landing.footer.platform')}>
          <a href="#how-it-works" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.nav.howItWorks')}
          </a>
          <a href="#data-sources" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.nav.dataSources')}
          </a>
          <Link to="/dashboard" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.nav.platformPreview')}
          </Link>
          <Link to="/login" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.nav.login')}
          </Link>
        </FooterColumn>

        <FooterColumn title={t('landing.footer.project')}>
          <Link to="/dashboard/provenance" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.footer.dataDictionary')}
          </Link>
          <Link to="/limitations" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.footer.limitations')}
          </Link>
          <Link to="/dashboard/validation" className={link} style={{ color: ON_BRAND_SOFT }}>
            {t('landing.footer.validation')}
          </Link>
        </FooterColumn>

        <FooterColumn title={t('landing.footer.contact')}>
          {/* dir="ltr" so the address does not reorder in Arabic. */}
          <a
            href="mailto:contact@aqabaaqua.ai"
            dir="ltr"
            className={link}
            style={{ color: ON_BRAND_SOFT, unicodeBidi: 'isolate' }}
          >
            contact@aqabaaqua.ai
          </a>
        </FooterColumn>
      </div>

      <p
        className="mx-auto mt-12 max-w-[1200px] border-t pt-6 text-xs"
        style={{ borderColor: FOOTER_RULE, color: FOOTER_INK_MUTED }}
      >
        {t('landing.footer.legal')}
      </p>
    </footer>
  );
}
