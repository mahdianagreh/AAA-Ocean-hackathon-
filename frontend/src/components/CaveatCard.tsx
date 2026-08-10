import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

/** The one shared treatment for a caveat, per Phase 8 Global Rule 2:
 *  icon (⚠ Warning / ℹ Note) + bold headline + explanation + source as a pill.
 *
 *  Built once here and reused on Pages 3 (Reef Zone detail), 5 (Reports) and 9
 *  (Site Scoring) — and anywhere else a caveat renders — so a caveat never turns
 *  back into plain inline gray text. `severity` drives the icon and the accent.
 *
 *  It carries NONE of the caveat's content itself: headline/body/source are
 *  passed in verbatim by the caller. The project rule is that a caveat's wording
 *  is the backend's, never paraphrased in the UI — this component only styles it.
 */

/** The severities the API is known to send; any other string reads as a note. */
export type CaveatSeverity = 'critical' | 'warning' | 'info' | 'note' | (string & {}) | null | undefined;

/** info and note are the same visual channel; anything unknown reads as a note. */
function normalise(severity: CaveatSeverity): 'critical' | 'warning' | 'note' {
  if (severity === 'critical') return 'critical';
  if (severity === 'warning') return 'warning';
  return 'note';
}

/** Accent colour as a CSS var — never a hex literal, and it reuses the hazard
 *  ramp so a critical caveat reads in the same language as a critical band. */
function accentVar(kind: 'critical' | 'warning' | 'note'): string {
  if (kind === 'critical') return 'var(--risk-critical)';
  if (kind === 'warning') return 'var(--risk-high)';
  return 'var(--hairline-2)';
}

/** Outline icons, 2px stroke, currentColor — the design-system icon contract. */
function CaveatIcon({ kind }: { kind: 'critical' | 'warning' | 'note' }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    className: 'shrink-0',
  };
  if (kind === 'note') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    );
  }
  // critical and warning share the triangle; colour separates them.
  return (
    <svg {...common}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export interface CaveatCardProps {
  /** Drives the icon and the accent colour. */
  severity?: CaveatSeverity;
  /** Bold plain-language headline. Optional — omit to lead with the body. */
  headline?: ReactNode;
  /** The explanation. `children` wins if both are given (for grouped content). */
  message?: string;
  children?: ReactNode;
  /** Rendered as a small pill beneath the body. */
  source?: string | null;
  /** The raw API field/key, kept only as small secondary detail. */
  field?: string | null;
  className?: string;
}

/** A single caveat, styled. See CaveatList for rendering a whole caveats[]. */
export function CaveatCard({
  severity,
  headline,
  message,
  children,
  source,
  field,
  className = '',
}: CaveatCardProps) {
  const { t } = useTranslation('tools');
  const kind = normalise(severity);
  const accent = accentVar(kind);
  // Known severities read as localized labels; an unexpected backend severity
  // (e.g. "advisory") is preserved verbatim rather than flattened to "Note", so
  // the UI never silently drops a distinction the backend expressed.
  const severityLabel =
    severity === 'critical'
      ? t('caveat.critical')
      : severity === 'warning'
        ? t('caveat.warning')
        : severity == null || severity === 'info' || severity === 'note'
          ? t('caveat.note')
          : String(severity);

  const body = children ?? (message ? <p className="m-0 max-w-prose text-xs text-ink-2">{message}</p> : null);

  return (
    <div
      data-caveat-card="true"
      data-severity={kind}
      className={`flex flex-col gap-2 glass-panel p-4 border-s-4 ${className}`}
      style={{ borderInlineStartColor: accent }}
    >
      <div className="flex items-start gap-2">
        <span style={{ color: accent }} className="mt-px">
          <CaveatIcon kind={kind} />
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <span
              className="text-2xs font-bold tracking-wider"
              style={{ color: kind === 'note' ? 'var(--ink-2)' : accent }}
            >
              {severityLabel.toUpperCase()}
            </span>
            {field ? (
              // ink-2 (not ink-3) for AA on the glass-panel surface-2 tint; dir=ltr
              // isolates the ID so it does not reorder under an Arabic layout.
              <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono text-2xs text-ink-2">
                {field}
              </span>
            ) : null}
          </div>
          {headline ? (
            <p className="m-0 text-xs font-semibold text-ink">{headline}</p>
          ) : null}
          {body}
        </div>
      </div>
      {source ? (
        <div className="flex flex-wrap items-center gap-2 ps-6">
          <span
            className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-2xs text-ink-2"
          >
            <span className="opacity-70">{t('caveat.source')}</span>
            <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono">
              {source}
            </span>
          </span>
        </div>
      ) : null}
    </div>
  );
}
