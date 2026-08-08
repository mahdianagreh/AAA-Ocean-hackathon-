import { useId } from 'react';

/** The AQABA AQUA AI mark. One component, three finishes — brand guidelines §2
 *  allows the full-colour gradient, navy, and white, and nothing else.
 *
 *  Every colour here is a raw brand hex rather than a theme token, and each is
 *  marked `token-ok:` for the tokens QA. That is deliberate and it is the same
 *  exemption map/style.ts holds: a trademark is fixed artwork. If the mark
 *  tracked --ink it would turn teal in dark theme, which brand guidelines §2
 *  lists under "Never — change colors".
 *
 *  The counters are cut with a <mask> rather than painted in the ground colour.
 *  A mark that fills its own negative space is only correct on the one
 *  background it was drawn against; this one has to sit on the white marketing
 *  nav, the navy dashboard rail and the gradient hero, and painting the counters
 *  would show as a pale wedge on two of the three.
 *
 *  Gradient IDs are per-instance via useId(). SVG ids are document-global, so
 *  two logos on one page with a hard-coded id both resolve to whichever mounted
 *  first — which reads as "the footer logo lost its gradient" and is a genuinely
 *  annoying bug to trace. */

type LogoVariant = 'gradient' | 'navy' | 'white';

const BRAND = {
  navy: '#0A1F4D', // token-ok: fixed brand artwork, must not track the theme
  aqua: '#00B7C3', // token-ok: fixed brand artwork, must not track the theme
  white: '#FFFFFF', // token-ok: fixed brand artwork, must not track the theme
} as const;

const MARK_ASPECT = 100 / 92;

export function LogoMark({
  size = 32,
  variant = 'gradient',
  className,
}: {
  size?: number;
  variant?: LogoVariant;
  className?: string;
}) {
  const uid = useId();
  const gradientId = `aq-logo-grad-${uid}`;
  const maskId = `aq-logo-mask-${uid}`;

  const fill =
    variant === 'gradient'
      ? `url(#${gradientId})`
      : variant === 'navy'
        ? BRAND.navy
        : BRAND.white;

  return (
    <svg
      width={Math.round(size * MARK_ASPECT)}
      height={size}
      viewBox="0 0 100 92"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={BRAND.aqua} />
          <stop offset="1" stopColor={BRAND.navy} />
        </linearGradient>
        {/* Mask luminance, not colour: white keeps, black cuts. These are
            greyscale stencil values, not brand colours. */}
        <mask id={maskId}>
          <rect x="0" y="0" width="100" height="92" fill="#000" /> {/* token-ok: mask stencil */}
          <path d="M50 4 L96 88 L4 88 Z" fill="#fff" /> {/* token-ok: mask stencil */}
          {/* The inner peak — the counter of the second A. */}
          <path d="M50 44 L66 78 L34 78 Z" fill="#000" /> {/* token-ok: mask stencil */}
          {/* The wave, cut clean through the mark so it still reads at 32px,
              which brand guidelines §2 sets as the digital minimum. */}
          <path d="M14 74 Q32 58 50 74 Q68 90 86 74" stroke="#000" strokeWidth="7" strokeLinecap="round" fill="none" /> {/* token-ok: mask stencil */}
        </mask>
      </defs>
      <rect x="0" y="0" width="100" height="92" fill={fill} mask={`url(#${maskId})`} />
    </svg>
  );
}

/** Mark plus wordmark, with the hairline divider from the brand sheet.
 *
 *  The wordmark is live text, not outlines: it switches weight with the theme,
 *  survives browser zoom, and is selectable and readable to a screen reader.
 *  `AI` takes the aqua accent in every finish except white monochrome, where a
 *  second colour would defeat the point of a monochrome lockup. */
export function Logo({
  size = 32,
  variant = 'gradient',
  showWordmark = true,
  className,
}: {
  size?: number;
  variant?: LogoVariant;
  showWordmark?: boolean;
  className?: string;
}) {
  if (!showWordmark) {
    return (
      <span className={className} role="img" aria-label="AQABA AQUA AI">
        <LogoMark size={size} variant={variant} />
      </span>
    );
  }

  const wordColour = variant === 'white' ? BRAND.white : BRAND.navy;
  const aiColour = variant === 'white' ? BRAND.white : BRAND.aqua;
  const divider =
    variant === 'white'
      ? 'rgb(255 255 255 / 0.5)'
      : `linear-gradient(180deg, ${BRAND.aqua}, ${BRAND.navy})`;

  return (
    <span
      className={className}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}
    >
      <LogoMark size={size} variant={variant} />
      <span
        aria-hidden="true"
        style={{ inlineSize: 1, blockSize: size * 0.7, background: divider }}
      />
      {/* dir="ltr" because the wordmark is a Latin trademark and must not
          reorder under <html dir="rtl">. */}
      <span
        dir="ltr"
        style={{
          fontWeight: 700,
          letterSpacing: '0.06em',
          fontSize: Math.max(13, Math.round(size * 0.44)),
          whiteSpace: 'nowrap',
          color: wordColour,
        }}
      >
        AQABA AQUA <span style={{ color: aiColour }}>AI</span>
      </span>
    </span>
  );
}
