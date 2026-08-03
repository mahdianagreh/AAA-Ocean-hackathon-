import type { ReactNode } from 'react';

/** The shared wrapper for the domain glyph set.
 *
 *  01 §8: these are line glyphs on the same hairline grid as the isobaths,
 *  because a catchment, a coastal outlet and a reef zone have no stock
 *  equivalents — reaching for a generic droplet or map pin would undo the
 *  signature. Lucide is for generic affordances only (close, chevron, search),
 *  and there is no emoji anywhere in this project.
 *
 *  `vector-effect="non-scaling-stroke"` keeps the stroke exactly 1px at every
 *  rendered size, which is what makes the glyphs share a language with the
 *  hairline borders rather than merely resembling them.
 */
export interface GlyphProps {
  size?: number;
  /** An accessible name. Omit only when the glyph sits beside its own label,
   *  in which case it is marked decorative rather than silently unlabelled. */
  label?: string;
  className?: string;
}

export function Glyph({
  size = 24,
  label,
  className,
  children,
}: GlyphProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1}
      strokeLinecap="round"
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={className}
      // The glyphs depict objects, not directions, so they do not mirror in
      // RTL — 06 §3. No transform here on purpose.
    >
      {children}
    </svg>
  );
}
