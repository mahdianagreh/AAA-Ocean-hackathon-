/** The AQABA AQUA AI mark. One component, three finishes — brand guidelines §2
 *  allows the full-colour gradient, navy, and white, and nothing else.
 *
 *  **This renders the real artwork, not a redrawing of it.** An earlier version of
 *  this file approximated the mark with hand-authored SVG paths: a triangle, a
 *  masked inner peak, one swept wave. It was close enough to look deliberate and
 *  wrong enough to be the wrong logo — the real mark carries two interlocking A
 *  letterforms and three distinct wave crests in its negative space, which is not
 *  something four path commands reproduce. The artwork now comes from
 *  `public/brand/logo-mark.png`, extracted from the brand lockup at its native
 *  422x371, so what ships is the mark the brand sheet specifies.
 *
 *  The two monochrome finishes are the same asset used as a CSS `mask-image`
 *  with a flat background colour behind it. That is why there is one file rather
 *  than three: the mask keys off the alpha channel, so the counters stay
 *  genuinely transparent and the ground shows through them. Painting the
 *  counters instead would show as a pale wedge on any ground the mark was not
 *  drawn against, and this one has to sit on the white marketing nav, the navy
 *  dashboard rail and the gradient hero.
 *
 *  The colours below are raw brand hexes rather than theme tokens, each marked
 *  `token-ok:` for the tokens QA. That is deliberate and it is the same exemption
 *  `map/style.ts` holds: a trademark is fixed artwork. A mark that tracked
 *  `--ink` would turn teal in dark theme, which brand guidelines §2 lists under
 *  "Never — change colors". */

type LogoVariant = 'gradient' | 'navy' | 'white';

const BRAND = {
  navy: '#0A1F4D', // token-ok: fixed brand artwork, must not track the theme
  aqua: '#00B7C3', // token-ok: fixed brand artwork, must not track the theme
  white: '#FFFFFF', // token-ok: fixed brand artwork, must not track the theme
} as const;

/** 422 / 371, the artwork's own proportions. Height is the controlled dimension
 *  so a logo sits on a text baseline predictably; width follows. */
const MARK_ASPECT = 422 / 371;
const MARK_SRC = '/brand/logo-mark.png';

export function LogoMark({
  size = 32,
  variant = 'gradient',
  className,
}: {
  size?: number;
  variant?: LogoVariant;
  className?: string;
}) {
  const width = Math.round(size * MARK_ASPECT);

  if (variant === 'gradient') {
    return (
      <img
        src={MARK_SRC}
        width={width}
        height={size}
        alt=""
        aria-hidden="true"
        decoding="async"
        className={className}
        style={{ display: 'block', objectFit: 'contain' }}
      />
    );
  }

  // Monochrome finishes: the artwork as an alpha mask over a flat brand colour.
  const mask = `url("${MARK_SRC}") no-repeat center / contain`;
  return (
    <span
      aria-hidden="true"
      className={className}
      style={{
        display: 'block',
        inlineSize: width,
        blockSize: size,
        backgroundColor: variant === 'white' ? BRAND.white : BRAND.navy,
        mask,
        WebkitMask: mask,
      }}
    />
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
