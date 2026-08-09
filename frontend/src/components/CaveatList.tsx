import { useTranslation } from 'react-i18next';

/** Renders a caveats[] array from any API response.
 *
 *  Every page Pulga owns receives caveats on the run AND on each result;
 *  both must surface. This component groups by severity, keeps the API's
 *  wording verbatim (caveats are not translated — a paraphrased caveat
 *  is no longer the caveat the backend stands behind). */

interface Caveat {
  field: string | null;
  message: string;
  severity: string | null;
  source: string | null;
}

function asCaveat(x: unknown): Caveat | null {
  if (!x || typeof x !== 'object') return null;
  const o = x as Record<string, unknown>;
  if (typeof o.message !== 'string') return null;
  return {
    field: typeof o.field === 'string' ? o.field : null,
    message: o.message,
    severity: typeof o.severity === 'string' ? o.severity : null,
    source: typeof o.source === 'string' ? o.source : null,
  };
}

const SEVERITY_ORDER = ['critical', 'warning', 'info'];

export function CaveatList({ items, title }: { items: unknown[]; title?: string }) {
  const { t } = useTranslation('tools');
  const rows = items.map(asCaveat).filter((c): c is Caveat => c !== null);
  if (rows.length === 0) return null;

  // Sort by severity: critical first
  rows.sort((a, b) => {
    const ai = SEVERITY_ORDER.indexOf(a.severity ?? 'info');
    const bi = SEVERITY_ORDER.indexOf(b.severity ?? 'info');
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <section className="flex flex-col gap-3" data-caveats="true">
      <h3 className="m-0 text-xs font-bold premium-gradient-text">
        {title ?? t('formula.caveatsTitle', { defaultValue: 'Caveats' })}
      </h3>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {rows.map((c, i) => (
          <li 
            key={`${c.field ?? 'caveat'}-${i}`} 
            className="flex flex-col gap-1 glass-panel p-4 transition-all duration-300 hover:glass-panel-hover border-s-4 hover:border-s-accent cursor-default group"
            style={{ borderInlineStartColor: c.severity === 'critical' ? 'var(--risk-critical)' : c.severity === 'warning' ? 'var(--risk-high)' : 'var(--hairline-2)' }}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-2xs font-bold tracking-wider" style={{ color: c.severity === 'critical' ? 'var(--risk-critical)' : c.severity === 'warning' ? 'var(--risk-high)' : 'var(--ink-2)' }}>
                {c.severity ? c.severity.toUpperCase() : 'INFO'}
              </span>
              {c.field ? (
                <>
                  <span className="text-ink-3 text-2xs">•</span>
                  <span className="text-2xs font-mono num text-ink-2 group-hover:text-accent transition-colors">{c.field}</span>
                </>
              ) : null}
            </div>
            <p className="m-0 max-w-prose text-xs text-ink-2">{c.message}</p>
            {c.source ? (
              <p className="m-0 mt-1 text-2xs text-ink-3">
                {t('provenance.source', { defaultValue: 'Source:' })} <span className="font-mono num opacity-80">{c.source}</span>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
