import { useTranslation } from 'react-i18next';
import type { EventRow } from '../api/live';
import { Link } from './Link';
import { ValueWithUnit } from './ValueWithUnit';
import { IdText } from '../routes/AlertsPage';

/** Rain-intensity ranking, at /events — the p4-08 view.
 *
 *  Ranks storms on `rank` / `max_daily_mm`, the canonical columns, and NEVER on
 *  max_anomaly_ratio, which is stale and ranks storms differently. One shared
 *  horizontal scale across all bars (the wettest storm sets the full width), so a
 *  longer bar means more rain — per-row scaling would make every storm look
 *  identical, the most common way a ranking chart lies.
 *
 *  The bar answers "how big"; `intensity_top_percent` answers "how unusual, here"
 *  — where this storm's depth sits in its wettest catchment's own ~28-year record,
 *  a real empirical percentile. The two are different questions and the demo event
 *  is the reason to show both: AQ-2016-10-28 is only mid-ranked by absolute depth
 *  yet sits in the top fraction of a percent of its catchment's days. It is the
 *  best-instrumented flood, not the biggest — the ranking places it where the data
 *  does, and nothing here calls it the largest.
 *
 *  One accent, no colour ramp (01 §3/§4). Provenance is form, not hue: the depth
 *  is measured, rendered through ValueWithUnit's solid rule.
 */
export function IntensityRanking({ rows, topN = 25 }: { rows: EventRow[]; topN?: number }) {
  const { t } = useTranslation('pages');

  const ranked = rows
    .filter((e) => e.rank !== null && e.max_daily_mm !== null)
    .sort((a, b) => (a.rank as number) - (b.rank as number))
    .slice(0, topN);

  if (!ranked.length) {
    return <p className="text-xs text-ink-3">{t('events.intensity.empty')}</p>;
  }

  const peak = Math.max(1e-6, ...ranked.map((e) => e.max_daily_mm as number));
  const hidden = rows.filter((e) => e.rank !== null).length - ranked.length;

  return (
    <div className="flex flex-col gap-3" data-intensity-ranking="true">
      <p className="m-0 max-w-prose text-2xs text-ink-2">{t('events.intensity.note')}</p>

      {/* Numbers and bars run LTR in both languages so the shared scale reads the
          same way — the row label mirrors with the layout, the scale does not. */}
      <ol className="m-0 flex list-none flex-col gap-1 p-0" dir="ltr">
        {ranked.map((e) => {
          const w = Math.max(2, ((e.max_daily_mm as number) / peak) * 100);
          // Documented storms (the ones that carry a literature name, e.g. the
          // demo event) get a quiet accent rail — they are the notable rows.
          const documented = !!e.label;
          return (
            <li
              key={e.event_id}
              className={[
                'group flex items-center gap-3 border-s-2 py-1.5 ps-2 text-xs transition-colors hover:bg-surface-2',
                documented ? 'border-accent' : 'border-transparent',
              ].join(' ')}
            >
              <span className="w-6 shrink-0 text-end font-mono num text-2xs text-ink-3">
                {e.rank}
              </span>
              <Link
                to={`/dashboard/replay/${encodeURIComponent(e.event_id)}`}
                className="w-28 shrink-0 truncate text-accent hover:underline"
                title={t('events.replayLink')}
              >
                <IdText>{e.event_id}</IdText>
              </Link>
              {/* One shared scale — a longer bar is more rain — in the brand's
                  data colour. The value sits after the bar, always on the
                  surface, so it never fights the fill for contrast. */}
              <div
                className="h-2.5 min-w-0 flex-1 overflow-hidden bg-surface-2"
                style={{ borderRadius: 'var(--radius-hairline)' }}
              >
                <span
                  className="block h-full bg-accent"
                  style={{ inlineSize: `${w}%`, borderRadius: 'var(--radius-hairline)' }}
                />
              </div>
              <ValueWithUnit
                value={e.max_daily_mm}
                unit={t('units.mmPerDay')}
                digits={1}
                provenance="measured"
                className="w-24 shrink-0 text-end"
              />
              <span className="w-14 shrink-0 truncate text-2xs text-ink-3">
                {e.wettest_catchment ? <IdText>{e.wettest_catchment}</IdText> : null}
              </span>
              {/* "How unusual, here": top N% of this catchment's own daily record. */}
              <span className="w-20 shrink-0 text-end">
                {/* `!= null`, not `!== null`. GET /api/v1/events does not serve
                    `intensity_top_percent` at all today — the field is absent from
                    the payload, so this reads `undefined`, which a strict !== null
                    check lets straight through into `.toLocaleString()`. That threw
                    and blanked the whole Intensity view. The loose check catches
                    both null and undefined, so a field the API has not shipped yet
                    renders as the honest gap instead of taking the page down. */}
                {e.intensity_top_percent != null ? (
                  <span
                    className="inline-block border border-hairline bg-surface px-1.5 py-0.5 text-2xs text-ink-2"
                    style={{ borderRadius: 'var(--radius-sm)' }}
                    title={t('events.intensity.topPercentHint')}
                  >
                    {t('events.intensity.topPercent', {
                      pct: e.intensity_top_percent.toLocaleString('en', {
                        maximumFractionDigits: 2,
                      }),
                    })}
                  </span>
                ) : (
                  <ValueWithUnit value={null} />
                )}
              </span>
            </li>
          );
        })}
      </ol>

      {hidden > 0 ? (
        <p className="m-0 text-2xs text-ink-3">{t('events.intensity.hidden', { n: hidden })}</p>
      ) : null}
    </div>
  );
}
