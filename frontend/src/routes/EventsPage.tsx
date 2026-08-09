import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchEvents,
  fetchSeasonalCalendar,
  type EventRow,
  type SeasonalCalendar as SeasonalCalendarData,
} from '../api/live';
import { IntensityRanking } from '../components/IntensityRanking';
import { Link } from '../components/Link';
import { SeasonalCalendar } from '../components/SeasonalCalendar';
import { Segmented } from '../components/Segmented';
import { Empty, ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';
import { Caveats, IdText } from './AlertsPage';

/** Three views of the one events domain, on one page: the searchable catalogue
 *  (p4-G), the rain-intensity ranking (p4-08), and the seasonal calendar (p4-K). */
type EventsView = 'catalogue' | 'intensity' | 'calendar';

/** The event catalogue, at /events.
 *
 *  `GET /api/v1/events` reads data/processed/events/events.parquet — 675 mined
 *  storms, the same table the runoff model trains against.
 *
 *  Two columns the API returns are deliberately NOT rendered.
 *
 *  `max_anomaly_ratio` is the important one: it is stale in the shipped parquet
 *  and the project docs say it must not be exposed. It would be the most
 *  quotable number on the page — "1.40× the seasonal normal" — which is exactly
 *  why leaving it in place "just as a column" is not neutral. Ranking is done on
 *  `rank` and `max_daily_mm`, both of which are current.
 *
 *  `mean_daily_mm` is omitted for a smaller reason: side by side with
 *  `max_daily_mm` and no per-catchment context, the pair reads as a range for
 *  one place when it is a maximum over catchments against a mean over the same
 *  set. The catchment the maximum belongs to IS shown (`wettest_catchment`), so
 *  the number on screen has an address.
 *
 *  There is no pagination on the endpoint, so the whole catalogue arrives in one
 *  response and the window is applied here. A truncation nobody is told about is
 *  a lie about the size of the record, so the count of hidden rows is stated
 *  whenever the filter matches more than the window.
 */

const WINDOW = 100;

type SortKey = 'rank' | 'date';
type SortDir = 'asc' | 'desc';

/** Nulls sort last in both directions. A missing rank is not rank zero. */
function cmpNullable(a: number | null, b: number | null, dir: SortDir): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return dir === 'asc' ? a - b : b - a;
}

function cmpDate(a: string | null, b: string | null, dir: SortDir): number {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  return dir === 'asc' ? a.localeCompare(b) : b.localeCompare(a);
}

function formatDate(iso: string, lang: 'en' | 'ar'): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-JO-u-nu-latn' : 'en-GB', {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(d);
}

export function EventsPage() {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';

  const [rows, setRows] = useState<EventRow[] | null>(null);
  // `null` rows plus `failed` distinguishes the three real states: still asking,
  // asked and the API is unreachable, asked and the catalogue is empty.
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('rank');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [view, setView] = useState<EventsView>('catalogue');
  const [calendar, setCalendar] = useState<SeasonalCalendarData | null>(null);

  useEffect(() => {
    let live = true;
    void fetchEvents().then((r) => {
      if (!live) return;
      if (r === null) setFailed(true);
      else setRows(r);
    });
    void fetchSeasonalCalendar().then((c) => {
      if (live) setCalendar(c);
    });
    return () => {
      live = false;
    };
  }, []);

  const matched = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    const hit = q
      ? rows.filter(
          (e) =>
            e.event_id.toLowerCase().includes(q) || (e.label ?? '').toLowerCase().includes(q),
        )
      : rows;
    return [...hit].sort((a, b) =>
      sortKey === 'rank'
        ? cmpNullable(a.rank, b.rank, sortDir)
        : cmpDate(a.start, b.start, sortDir),
    );
  }, [rows, query, sortKey, sortDir]);

  const shown = matched.slice(0, WINDOW);
  const hidden = matched.length - shown.length;

  const caveats = useMemo(() => {
    const seen = new Set<string>();
    const out: unknown[] = [];
    for (const e of matched) {
      for (const c of e.caveats ?? []) {
        const key = JSON.stringify(c);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(c);
      }
    }
    return out;
  }, [matched]);

  const toggle = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      // Rank 1 is the strongest storm, so rank ascends by default; dates start
      // at the most recent, which is what a person scanning a feed expects.
      setSortDir(key === 'rank' ? 'asc' : 'desc');
    }
  };

  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' =>
    sortKey !== key ? 'none' : sortDir === 'asc' ? 'ascending' : 'descending';

  return (
    <PageShell title={t('events.title')} lede={t('events.lede')}>
      <div data-events-view={view}>
        <Segmented<EventsView>
          label={t('events.viewLabel')}
          value={view}
          onChange={setView}
          options={[
            { value: 'catalogue', label: t('events.view.catalogue') },
            { value: 'intensity', label: t('events.view.intensity') },
            { value: 'calendar', label: t('events.view.calendar') },
          ]}
        />
      </div>

      {view === 'intensity' ? (
        <Section label={t('events.intensity.title')}>
          {failed ? (
            <ErrorState what={t('events.errorTitle')} message={t('events.errorBody')} />
          ) : rows === null ? (
            <Loading what={t('events.loading')} />
          ) : (
            <IntensityRanking rows={rows} />
          )}
        </Section>
      ) : null}

      {view === 'calendar' ? (
        <Section label={t('events.calendar.title')}>
          {calendar === null ? (
            <Loading what={t('events.calendar.loading')} />
          ) : (
            <SeasonalCalendar data={calendar} />
          )}
        </Section>
      ) : null}

      {view === 'catalogue' ? (
        <>
      <Section label={t('events.filterLabel')}>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="events-filter" className="text-2xs font-semibold text-ink-2">
              {t('events.filterFieldLabel')}
            </label>
            <input
              id="events-filter"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('events.filterPlaceholder')}
              className="min-h-8 min-w-64 rounded-sm border border-hairline bg-surface px-2 py-1 text-xs text-ink"
            />
          </div>
          {rows ? (
            <p className="m-0 text-2xs text-ink-2">
              {t('events.count', { shown: shown.length, total: rows.length })}
            </p>
          ) : null}
        </div>
        {hidden > 0 ? (
          <p className="m-0 text-2xs text-ink-2">{t('events.hidden', { n: hidden })}</p>
        ) : null}
      </Section>

      <Section label={t('events.tableLabel')}>
        {failed ? (
          <ErrorState what={t('events.errorTitle')} message={t('events.errorBody')} />
        ) : rows === null ? (
          <Loading what={t('events.loading')} />
        ) : matched.length === 0 ? (
          <Empty
            title={rows.length === 0 ? t('events.emptyTitle') : t('events.noMatchTitle')}
            body={rows.length === 0 ? t('events.emptyBody') : t('events.noMatchBody')}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <caption className="sr-only">{t('events.tableCaption')}</caption>
              <thead>
                <tr className="border-b border-hairline text-2xs text-ink-2">
                  <th scope="col" className="p-2 text-start font-semibold">
                    {t('events.col.id')}
                  </th>
                  <th scope="col" aria-sort={ariaSort('date')} className="p-2 text-start font-semibold">
                    <button
                      type="button"
                      onClick={() => toggle('date')}
                      className="text-2xs font-semibold text-ink-2 underline"
                    >
                      {t('events.col.start')}
                    </button>
                  </th>
                  <th scope="col" className="p-2 text-start font-semibold">
                    {t('events.col.label')}
                  </th>
                  <th scope="col" aria-sort={ariaSort('rank')} className="p-2 text-start font-semibold">
                    <button
                      type="button"
                      onClick={() => toggle('rank')}
                      className="text-2xs font-semibold text-ink-2 underline"
                    >
                      {t('events.col.rank')}
                    </button>
                  </th>
                  <th scope="col" className="p-2 text-start font-semibold">
                    {t('events.col.maxDaily')}
                  </th>
                  <th scope="col" className="p-2 text-start font-semibold">
                    {t('events.col.wettest')}
                  </th>
                  <th scope="col" className="p-2 text-start font-semibold">
                    {t('events.col.stormDays')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => {
                  const started = e.start ? formatDate(e.start, lang) : null;
                  return (
                    <tr key={e.event_id} className="border-b border-hairline align-top">
                      <th scope="row" className="p-2 text-start font-normal">
                        <Link
                          to={`/dashboard/replay/${encodeURIComponent(e.event_id)}`}
                          className="underline"
                          title={t('events.replayLink')}
                        >
                          <IdText>{e.event_id}</IdText>
                        </Link>
                      </th>
                      <td className="p-2">
                        {e.start && started ? (
                          <time dateTime={e.start} className="text-ink-2">
                            {started}
                          </time>
                        ) : (
                          <ValueWithUnit value={null} />
                        )}
                      </td>
                      <td className="max-w-prose p-2">
                        {e.label ?? (
                          <span className="text-ink-3" title={t('events.noLabelHint')}>
                            {t('events.noLabel')}
                          </span>
                        )}
                      </td>
                      <td className="p-2">
                        <ValueWithUnit value={e.rank} digits={0} provenance="measured" />
                      </td>
                      <td className="p-2">
                        <ValueWithUnit
                          value={e.max_daily_mm}
                          digits={1}
                          unit={t('units.mmPerDay')}
                          provenance="measured"
                        />
                      </td>
                      <td className="p-2">
                        {e.wettest_catchment ? (
                          <IdText>{e.wettest_catchment}</IdText>
                        ) : (
                          <ValueWithUnit value={null} />
                        )}
                      </td>
                      <td className="p-2">
                        <ValueWithUnit
                          value={e.storm_days}
                          digits={0}
                          unit={t('units.days')}
                          provenance="measured"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="m-0 max-w-prose text-2xs text-ink-3">{t('events.rankingNote')}</p>
      </Section>

      {caveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <Caveats items={caveats} />
        </Section>
      ) : null}
        </>
      ) : null}
    </PageShell>
  );
}
