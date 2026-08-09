import { useTranslation } from 'react-i18next';
import type { RainPoint } from '../api/event';
import { ValueWithUnit } from './ValueWithUnit';

/** Rainfall over the event window, as small multiples — one row per catchment.
 *
 *  WHY NOT FIVE COLOURED SERIES ON ONE AXIS:
 *  01 §4 allows exactly one accent and says plainly it is not a data colour, and
 *  01 §3 rejects a colour ramp used decoratively. Five overlaid series would need
 *  five categorical hues this design system deliberately does not have. Small
 *  multiples answer the actual question better anyway — the officer wants "which
 *  catchment is worse", which is a comparison of shapes at a shared scale, not a
 *  spaghetti plot.
 *
 *  ONE SHARED SCALE, and it is load-bearing. Every row is scaled to the same
 *  maximum, so a taller bar means more rain. Per-row auto-scaling would make five
 *  catchments with very different totals look identical, which is the single most
 *  common way small multiples lie.
 *
 *  ONE AXIS, never two. The mooring's turbidity is not overlaid on a second
 *  y-scale — it appears as a marker on the *time* axis, because a dual-axis chart
 *  invites the reader to see a correlation the geometry invented.
 *
 *  Bars, not a line: daily totals are discrete accumulations over a bounded
 *  interval, and a line between them would imply we know the shape in between. We
 *  do not — there is no sub-daily series in the repo.
 */
interface Props {
  byCatchment: Record<string, RainPoint[]>;
  unit: string;
  cursor: number;
  onCursor: (i: number) => void;
  /** Timestamps of measured marks, drawn on the shared time axis. */
  marks?: Array<{ t: string; label: string }>;
}

export function Hyetograph({ byCatchment, unit, cursor, onCursor, marks = [] }: Props) {
  const { t } = useTranslation();
  const ids = Object.keys(byCatchment).sort();
  const rows = ids.map((id) => ({ id, points: byCatchment[id] }));
  const steps = rows[0]?.points.length ?? 0;

  // The shared maximum, across every catchment and every step.
  const peak = Math.max(
    1e-6,
    ...rows.flatMap((r) => r.points.map((p) => p.mm ?? 0)),
  );

  if (!steps) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  return (
    <div className="flex flex-col gap-2 glass-card p-3 hover:glass-card-hover transition-all duration-300">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-bold premium-gradient-text">{t('chart.hyetograph')}</h3>
        {/* One direct label rather than a number on every bar — the peak is the
            figure a reader wants, and labelling all 25 would be noise. */}
        <span className="text-2xs font-medium text-ink-3">
          {t('chart.peak')} <ValueWithUnit value={peak} unit={unit} digits={2} provenance="modelled" />
        </span>
      </div>

      {/* Time runs left to right, in both languages — 06 §3. The rows mirror with
          the layout; the axis inside them does not. */}
      <div dir="ltr" className="flex flex-col gap-1">
        {rows.map(({ id, points }) => (
          <div key={id} className="flex items-center gap-2">
            <span className="w-14 shrink-0 font-mono num text-2xs text-ink-3">{id}</span>

            <div className="relative flex h-7 min-w-0 flex-1 items-end gap-px">
              {points.map((p, i) => {
                const missing = p.mm === null;
                const h = missing ? 0 : Math.max(1, (p.mm! / peak) * 100);
                const active = i === cursor;
                return (
                  <button
                    key={p.t}
                    type="button"
                    onClick={() => onCursor(i)}
                    title={`${p.t} · ${missing ? t('value.missing') : `${p.mm!.toFixed(2)} ${unit}`}`}
                    aria-label={`${id} ${p.t} ${missing ? t('value.missing') : `${p.mm!.toFixed(2)} ${unit}`}`}
                    aria-pressed={active}
                    // The 1px gap between bars is the surface showing through, not
                    // a border — adjacent fills need separating without a line.
                    className="group relative flex h-full min-w-0 flex-1 items-end"
                  >
                    {missing ? (
                      // A gap renders as a gap. Hatched, never a zero-height bar
                      // that reads as "it did not rain" — 09 rule 4.
                      <span
                        className="block h-full w-full opacity-60"
                        style={{
                          backgroundImage:
                            'repeating-linear-gradient(45deg, var(--data-modelled) 0 1px, transparent 1px 4px)',
                        }}
                      />
                    ) : (
                      <span
                        className={`block w-full transition-all duration-300 ${active ? 'brand-gradient neon-glow' : 'bg-ink-3 opacity-60'} group-hover:brand-gradient group-hover:opacity-100 hover:-translate-y-1`}
                        // 4px rounded data-end, anchored to the baseline.
                        style={{ height: `${h}%`, borderStartStartRadius: 4, borderStartEndRadius: 4 }}
                      />
                    )}
                  </button>
                );
              })}

              {/* The cursor line, spanning the row so the choreography is visible
                  even on a catchment whose bar is short at this step. */}
              <span
                aria-hidden="true"
                className="pointer-events-none absolute inset-y-0 w-px bg-accent/50 neon-glow"
                style={{
                  insetInlineStart: `${((cursor + 0.5) / steps) * 100}%`,
                }}
              />
            </div>
          </div>
        ))}

        {/* The shared time axis, once, beneath all five rows. */}
        <div className="ms-16 flex items-start justify-between border-t border-hairline pt-0.5">
          {rows[0]!.points.map((p, i) => (
            <span
              key={p.t}
              className={`font-mono num text-2xs ${i === cursor ? 'text-accent' : 'text-ink-3'}`}
            >
              {p.t.slice(8, 10)}
            </span>
          ))}
        </div>

        {marks.length ? (
          <p className="ms-16 flex flex-wrap gap-3 text-2xs text-ink-3">
            {marks.map((m) => (
              <span key={m.t} className="flex items-center gap-1">
                {/* Solid = measured. Same form language as the map and the
                    provenance legend. */}
                <svg width="10" height="8" aria-hidden="true">
                  <line x1="5" y1="0" x2="5" y2="8" stroke="var(--data-measured)" strokeWidth="1.5" />
                </svg>
                {m.label}
              </span>
            ))}
          </p>
        ) : null}
      </div>
    </div>
  );
}
