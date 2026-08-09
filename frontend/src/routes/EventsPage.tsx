import { useEffect, useMemo, useState, type ReactNode } from 'react';
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
import { Select } from '../components/Select';
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

/** A sortable column header: the label plus an arrow that appears only on the
 *  active column and points the current way. Colour is not the only signal —
 *  the arrow is. */
function SortButton({
  active,
  dir,
  onClick,
  end,
  children,
}: {
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  end?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'inline-flex items-center gap-1 text-2xs font-semibold uppercase tracking-wide transition-colors',
        end ? 'flex-row-reverse' : '',
        active ? 'text-accent' : 'text-ink-3 hover:text-ink-2',
      ].join(' ')}
    >
      {children}
      <span aria-hidden="true" className="font-mono">
        {active ? (dir === 'asc' ? '↑' : '↓') : ''}
      </span>
    </button>
  );
}

export function EventsPage() {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';

  const [rows, setRows] = useState<EventRow[] | null>(null);
  // `null` rows plus `failed` distinguishes the three real states: still asking,
  // asked and the API is unreachable, asked and the catalogue is empty.
  const [failed, setFailed] = useState(false);
  // Filter by selection, not by typing an ID: catchment, year, and whether the
  // storm carries a literature label. 'all' is the unset value for the dropdowns.
  const [catchment, setCatchment] = useState('all');
  const [year, setYear] = useState('all');
  const [labelledOnly, setLabelledOnly] = useState(false);
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

  // Options come from the data, not a hardcoded list — a catchment or year with
  // no storms never appears as a dead choice.
  const catchmentOptions = useMemo(() => {
    const ids = [...new Set((rows ?? []).map((e) => e.wettest_catchment).filter(Boolean))].sort();
    return [
      { value: 'all', label: t('events.filter.allCatchments') },
      ...ids.map((id) => ({ value: id as string, label: id as string })),
    ];
  }, [rows, t]);

  const yearOptions = useMemo(() => {
    const years = [...new Set((rows ?? []).map((e) => e.start?.slice(0, 4)).filter(Boolean))]
      .sort()
      .reverse();
    return [
      { value: 'all', label: t('events.filter.allYears') },
      ...years.map((y) => ({ value: y as string, label: y as string })),
    ];
  }, [rows, t]);

  const matched = useMemo(() => {
    if (!rows) return [];
    const hit = rows.filter(
      (e) =>
        (catchment === 'all' || e.wettest_catchment === catchment) &&
        (year === 'all' || (e.start ?? '').startsWith(year)) &&
        (!labelledOnly || !!e.label),
    );
    return [...hit].sort((a, b) =>
      sortKey === 'rank'
        ? cmpNullable(a.rank, b.rank, sortDir)
        : cmpDate(a.start, b.start, sortDir),
    );
  }, [rows, catchment, year, labelledOnly, sortKey, sortDir]);

  const shown = matched.slice(0, WINDOW);
  const hidden = matched.length - shown.length;
  const filtered = catchment !== 'all' || year !== 'all' || labelledOnly;
  // Shared scale for the inline intensity bar, so a longer bar means more rain
  // across the whole visible table — the same rule the ranking view follows.
  const peakDaily = Math.max(1e-6, ...shown.map((e) => e.max_daily_mm ?? 0));

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
        <div className="flex flex-wrap items-center gap-2">
          <Select
            label={t('events.filter.catchmentLabel')}
            value={catchment}
            onChange={setCatchment}
            options={catchmentOptions}
          />
          <Select
            label={t('events.filter.yearLabel')}
            value={year}
            onChange={setYear}
            options={yearOptions}
          />
          <button
            type="button"
            aria-pressed={labelledOnly}
            onClick={() => setLabelledOnly((v) => !v)}
            className={[
              'inline-flex min-h-9 items-center gap-1.5 border px-3 text-xs transition-colors',
              labelledOnly
                ? 'border-accent bg-surface-2 font-semibold text-ink'
                : 'border-hairline bg-surface text-ink-2 hover:border-hairline-2',
            ].join(' ')}
            style={{ borderRadius: 'var(--radius-md)' }}
          >
            <span
              aria-hidden="true"
              className={`inline-block h-2.5 w-2.5 rounded-full border ${labelledOnly ? 'border-accent bg-accent' : 'border-hairline-2'}`}
            />
            {t('events.filter.labelledOnly')}
          </button>
          {filtered ? (
            <button
              type="button"
              onClick={() => {
                setCatchment('all');
                setYear('all');
                setLabelledOnly(false);
              }}
              className="min-h-9 px-2 text-2xs text-ink-3 underline hover:text-ink-2"
            >
              {t('events.filter.reset')}
            </button>
          ) : null}
          {rows ? (
            <p className="m-0 ms-auto text-2xs text-ink-2">
              {t('events.count', { shown: shown.length, total: matched.length })}
            </p>
          ) : null}
        </div>
        {hidden > 0 ? (
          <p className="m-0 mt-1 text-2xs text-ink-3">{t('events.hidden', { n: hidden })}</p>
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
          <div className="overflow-x-auto rule" style={{ borderRadius: 'var(--radius-md)' }}>
            <table className="w-full border-collapse text-xs">
              <caption className="sr-only">{t('events.tableCaption')}</caption>
              <thead>
                <tr className="border-b border-hairline bg-surface-2 text-2xs uppercase tracking-wide text-ink-3">
                  <th scope="col" className="px-3 py-2 text-start font-semibold">
                    {t('events.col.id')}
                  </th>
                  <th scope="col" aria-sort={ariaSort('date')} className="px-3 py-2 text-start font-semibold">
                    <SortButton active={sortKey === 'date'} dir={sortDir} onClick={() => toggle('date')}>
                      {t('events.col.start')}
                    </SortButton>
                  </th>
                  <th scope="col" aria-sort={ariaSort('rank')} className="px-3 py-2 text-end font-semibold">
                    <SortButton active={sortKey === 'rank'} dir={sortDir} onClick={() => toggle('rank')} end>
                      {t('events.col.rank')}
                    </SortButton>
                  </th>
                  <th scope="col" className="px-3 py-2 text-end font-semibold">
                    {t('events.col.maxDaily')}
                  </th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">
                    {t('events.col.wettest')}
                  </th>
                  <th scope="col" className="px-3 py-2 text-end font-semibold">
                    {t('events.col.stormDays')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => {
                  const started = e.start ? formatDate(e.start, lang) : null;
                  const barW = e.max_daily_mm ? Math.max(3, (e.max_daily_mm / peakDaily) * 100) : 0;
                  return (
                    <tr
                      key={e.event_id}
                      className="border-b border-hairline transition-colors last:border-0 hover:bg-surface-2"
                    >
                      <th scope="row" className="px-3 py-2.5 text-start font-normal">
                        <Link
                          to={`/dashboard/replay/${encodeURIComponent(e.event_id)}`}
                          className="text-accent hover:underline"
                          title={t('events.replayLink')}
                        >
                          <IdText>{e.event_id}</IdText>
                        </Link>
                        {e.label ? (
                          <span
                            className="ms-2 inline-block border border-accent px-1.5 py-0.5 text-2xs align-middle text-accent"
                            style={{ borderRadius: 'var(--radius-sm)' }}
                            title={t('events.labelledHint')}
                          >
                            {t('events.labelledChip')}
                          </span>
                        ) : null}
                      </th>
                      <td className="px-3 py-2.5 text-ink-2">
                        {e.start && started ? (
                          <time dateTime={e.start}>{started}</time>
                        ) : (
                          <ValueWithUnit value={null} />
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-end">
                        {e.rank !== null ? (
                          <span
                            className="inline-block min-w-7 bg-surface-2 px-1.5 py-0.5 text-center font-mono num text-ink"
                            style={{ borderRadius: 'var(--radius-sm)' }}
                          >
                            {e.rank}
                          </span>
                        ) : (
                          <ValueWithUnit value={null} />
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-end">
                        <div className="flex items-center justify-end gap-2">
                          <span
                            aria-hidden="true"
                            className="hidden h-1.5 bg-accent sm:block"
                            style={{ inlineSize: `${barW}%`, maxInlineSize: '5rem', borderRadius: 'var(--radius-hairline)' }}
                          />
                          <ValueWithUnit
                            value={e.max_daily_mm}
                            digits={1}
                            unit={t('units.mmPerDay')}
                            provenance="measured"
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        {e.wettest_catchment ? (
                          <IdText>{e.wettest_catchment}</IdText>
                        ) : (
                          <ValueWithUnit value={null} />
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-end">
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
        <p className="m-0 mt-2 max-w-prose text-2xs text-ink-3">{t('events.rankingNote')}</p>
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
