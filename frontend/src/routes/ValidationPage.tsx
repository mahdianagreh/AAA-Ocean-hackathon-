import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { DataTable, type Column } from '../components/DataTable';
import { Timeline } from '../components/Timeline';
import { fetchEvents, fetchMooring, type EventRow } from '../api/live';
import { loadEventSeries } from '../api/event';
import { loadValidation, type Validation } from '../api/panels';
import type { Provenance } from '../api/types';

/** Modelled versus measured, at /dashboard/validation.
 *
 *  The overlay panel (src/panels/ValidationPanel.tsx) still exists and still
 *  reads the committed validation fixture — it is the mid-demo lookup from the
 *  map screen and is deliberately untouched. This page is the route-level
 *  presentation of the same material with one substantive difference, which is
 *  the reason it does not simply embed the panel:
 *
 *    THE MEASURED COLUMN IS LIVE. It comes from
 *    GET /api/v1/events/{id}/mooring, not from a fixture. That was the known
 *    unfinished task, and embedding the panel would have kept a fixture on
 *    screen while claiming to show the real record.
 *
 *  Only AQ-2016-10-28 has a mooring record; every other event 404s by design.
 *  A 404 is therefore rendered as "no measured record for this event", not as an
 *  error — the event selector exists so that state is reachable and legible
 *  rather than theoretical.
 *
 *  The anchor event id is read from the committed event series rather than typed
 *  here, per the project rule that no date is hard-coded.
 *
 *  The satellite section is a finding, not an omission. It is driven by the
 *  repo's own event audit (docs/event_audit.md, via the derived validation
 *  record) so the verdict on screen is the verdict in the document.
 */

interface MooringValue {
  value: number | null;
  unit: string;
  provenance: Provenance;
  uncertainty?: { sigma?: number; lower?: number; upper?: number } | null;
}

interface MooringMarker {
  key: string;
  t: string;
  provenance: Provenance;
}

interface MooringCaveat {
  field: string;
  message: string;
  severity: string;
  source?: string | null;
}

interface MooringLive {
  event_id: string;
  source_citation: string;
  source_doi: string;
  source_file: string;
  position: {
    lon: number;
    lat: number;
    crs?: string;
    depth_m: number;
    uncertainty_radius_m: number;
    provenance: string;
    note?: string;
    derivation_doc?: string;
  };
  markers: MooringMarker[];
  elevated_duration_hours: MooringValue;
  peak_suspended_sediment: MooringValue;
  salinity_minimum: MooringValue;
  salinity_anomaly: MooringValue;
  sediment_mass_total: MooringValue;
  series_available: boolean;
  caveats: MooringCaveat[];
}

type MooringState =
  | { kind: 'loading' }
  | { kind: 'none' }
  | { kind: 'ok'; record: MooringLive };

/** The five measured quantities, in the order the paper reports them. Kept as a
 *  list rather than five hand-written rows so the plain-text statements and the
 *  field table cannot drift apart. */
const FIELDS = [
  'salinity_anomaly',
  'salinity_minimum',
  'peak_suspended_sediment',
  'elevated_duration_hours',
  'sediment_mass_total',
] as const;

type FieldKey = (typeof FIELDS)[number];

const DIGITS: Record<FieldKey, number> = {
  salinity_anomaly: 2,
  salinity_minimum: 2,
  peak_suspended_sediment: 2,
  elevated_duration_hours: 2,
  sediment_mass_total: 0,
};

export function ValidationPage() {
  const { t } = useTranslation('tools');
  const selectId = useId();

  const [eventId, setEventId] = useState<string | null>(null);
  const [events, setEvents] = useState<EventRow[] | null>(null);
  const [mooring, setMooring] = useState<MooringState>({ kind: 'loading' });
  const [record, setRecord] = useState<Validation | null>(null);

  // The anchor event and the selectable list. Both best-effort: if the events
  // endpoint is unreachable the page still works against the anchor alone.
  useEffect(() => {
    let live = true;
    void loadEventSeries()
      .then((s) => live && setEventId(s.event_id))
      .catch(() => {
        /* the selector falls back to whatever the events list offers */
      });
    void fetchEvents().then((rows) => live && setEvents(rows));
    void loadValidation()
      .then((v) => live && setRecord(v))
      .catch(() => {
        /* the satellite/calibration sections render their own absent state */
      });
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (!eventId) return;
    let live = true;
    setMooring({ kind: 'loading' });
    void fetchMooring(eventId).then((raw) => {
      if (!live) return;
      setMooring(raw ? { kind: 'ok', record: raw as unknown as MooringLive } : { kind: 'none' });
    });
    return () => {
      live = false;
    };
  }, [eventId]);

  const options = events?.length
    ? events.map((e) => e.event_id)
    : eventId
      ? [eventId]
      : [];

  return (
    <PageShell title={t('validation.title')} lede={t('validation.lede')}>
      <Section label={t('validation.eventSection')}>
        <Card>
          <label htmlFor={selectId} className="text-xs font-semibold">
            {t('validation.eventLabel')}
          </label>
          <select
            id={selectId}
            className="w-full max-w-xs rounded-md border border-hairline bg-surface/50 px-3 py-2 text-sm text-ink hover:border-accent focus:border-accent outline-none transition-colors"
            value={eventId ?? ''}
            onChange={(e) => setEventId(e.target.value)}
            disabled={!options.length}
          >
            {options.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <p className="m-0 text-xs text-ink-2">{t('validation.eventHint')}</p>
        </Card>
      </Section>

      <Section label={t('validation.measuredSection')}>
        {mooring.kind === 'loading' ? (
          <p className="m-0 text-xs text-ink-3" aria-live="polite">
            {t('validation.loading')}
          </p>
        ) : mooring.kind === 'none' ? (
          <Card>
            <h3 className="m-0 text-sm font-semibold">{t('validation.noRecordTitle')}</h3>
            <p className="m-0 max-w-prose text-xs text-ink-2">
              {t('validation.noRecordBody', { eventId: eventId ?? '' })}
            </p>
            <p className="m-0 text-2xs text-ink-3">{t('validation.noRecordNotError')}</p>
          </Card>
        ) : (
          <MeasuredRecord record={mooring.record} />
        )}
      </Section>

      <Section label={t('validation.modelledSection')}>
        <Card>
          <h3 className="m-0 text-sm font-semibold">{t('validation.modelledTitle')}</h3>
          <p className="m-0 max-w-prose text-xs text-ink-2">{t('validation.modelledBody')}</p>
          {record ? (
            <p className="m-0 text-2xs text-ink-3">
              {t('validation.blockedOn')}{' '}
              <code dir="ltr" className="font-mono num">
                {record.modelled_blocked_on}
              </code>
            </p>
          ) : null}
        </Card>

        {record?.calibration_fit ? (
          <Card>
            <h3 className="m-0 text-sm font-semibold">{t('validation.calibrationTitle')}</h3>
            <p className="m-0 max-w-prose text-xs text-ink-2">
              {t('validation.calibrationBody', { n: record.calibration_fit.n_trials })}
            </p>
            {/* Measured-vs-modelled timing, as a chart of how far the modelled
                arrival/duration/peak fall from the measured record. Real API
                error values; modelled provenance means the bars read dashed-hue,
                distinct from any measured mark. Magnitude bars fill from the
                inline-start, so the chart mirrors cleanly under RTL. */}
            {/* Not role="img": each row's label and its ValueWithUnit magnitude
                must stay readable to assistive tech — only the bar itself is
                decorative (aria-hidden). The section heading names it. */}
            <div className="flex flex-col gap-2">
              {(
                [
                  ['arrival', record.calibration_fit.arrival_time_error_hours],
                  ['duration', record.calibration_fit.duration_error_hours],
                  ['peak', record.calibration_fit.peak_timing_error_hours],
                ] as const
              ).map(([key, value], _i, arr) => {
                const maxAbs = Math.max(0.5, ...arr.map(([, v]) => Math.abs(v ?? 0)));
                const pct = value == null ? 0 : (Math.abs(value) / maxAbs) * 100;
                return (
                  <div key={key} className="flex items-center gap-3 text-xs">
                    <span className="w-20 shrink-0 text-ink-2">{t(`validation.calibration.${key}`)}</span>
                    <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                      <span
                        className="absolute inset-y-0 start-0 rounded-full"
                        style={{ width: `${pct}%`, background: 'var(--data-modelled)' }}
                      />
                    </span>
                    <span className="w-20 shrink-0 text-end">
                      <ValueWithUnit value={value} unit="h" digits={2} provenance="modelled" />
                    </span>
                  </div>
                );
              })}
            </div>
            {/* Caveats verbatim from the calibration record — sourced prose, not
                UI chrome, so they are not run through i18n. */}
            <p className="m-0 max-w-prose text-2xs text-ink-2">
              {record.calibration_fit.peak_timing_caveat}
            </p>
            <p className="m-0 max-w-prose text-2xs text-ink-2">
              {record.calibration_fit.windage_caveat}
            </p>
            {record.calibration_fit.forcing_is_placeholder ? (
              <p className="m-0 max-w-prose text-2xs font-semibold text-ink">
                {t('validation.forcingPlaceholder')}{' '}
                <span className="font-normal text-ink-2">
                  {record.calibration_fit.forcing_placeholder_reason}
                </span>
              </p>
            ) : null}
            <p className="m-0 text-2xs text-ink-3">
              {t('validation.source')}{' '}
              <code dir="ltr" className="font-mono num">
                {record.calibration_fit.source}
              </code>
            </p>
          </Card>
        ) : null}
      </Section>

      <Section label={t('validation.satelliteSection')}>
        <Card>
          <h3 className="m-0 flex flex-wrap items-baseline gap-2 text-sm font-semibold">
            {t('validation.satelliteTitle')}
            <span className="rounded-sm border border-risk-high-stroke bg-risk-high px-1.5 py-0.5 text-2xs font-bold text-risk-high-on">
              {record?.satellite.verdict ?? t('validation.satelliteVerdict')}
            </span>
          </h3>
          <p className="m-0 max-w-prose text-xs text-ink-2">{t('validation.satelliteBody')}</p>
          <ul className="m-0 flex list-disc flex-col gap-1 ps-5 text-xs text-ink-2">
            <li>{t('validation.satelliteElevated')}</li>
            <li>{t('validation.satellitePassOne')}</li>
            <li>{t('validation.satellitePassTwo')}</li>
          </ul>
          <p className="m-0 max-w-prose text-xs">
            <strong className="font-semibold">{t('validation.physicalNull')}</strong>{' '}
            <span className="text-ink-2">{t('validation.physicalNullBody')}</span>
          </p>
          {record ? (
            <>
              <blockquote
                dir="ltr"
                className="m-0 max-w-prose whitespace-pre-line border-s-2 border-data-measured ps-3 text-2xs text-ink-2"
              >
                {record.satellite.excerpt}
              </blockquote>
              <p className="m-0 text-2xs text-ink-3">
                {t('validation.source')}{' '}
                <code dir="ltr" className="font-mono num">
                  {record.satellite.source}
                </code>
              </p>
            </>
          ) : null}
        </Card>
      </Section>
    </PageShell>
  );
}

function MeasuredRecord({ record }: { record: MooringLive }) {
  const { t } = useTranslation('tools');

  // Measured-quantities table on the shared DataTable (Page 2's pattern). Every
  // value carries its provenance through ValueWithUnit (measured solid / reported
  // / converted / modelled), so "source vs derived" survives the redesign, and
  // the provenance column names it in words as well.
  const fieldColumns: Column<FieldKey>[] = [
    {
      key: 'quantity',
      header: t('validation.quantity'),
      cardLabel: t('validation.quantity'),
      cell: (key) => t(`validation.field.${key}`),
    },
    {
      key: 'measured',
      align: 'end',
      header: t('validation.measured'),
      cell: (key) => (
        <ValueWithUnit
          value={record[key].value}
          unit={record[key].unit}
          digits={DIGITS[key]}
          provenance={record[key].provenance}
        />
      ),
    },
    {
      key: 'provenance',
      header: t('validation.provenanceLabel'),
      cell: (key) => t(`common:provenance.${record[key].provenance}`),
    },
    {
      key: 'uncertainty',
      header: t('validation.uncertaintyLabel'),
      cell: (key) => {
        const u = record[key].uncertainty;
        if (u?.sigma !== undefined && u.sigma !== null) {
          return (
            <span>
              {t('validation.sigma')} <ValueWithUnit value={u.sigma} digits={0} />
            </span>
          );
        }
        if (u?.lower !== undefined && u.upper !== undefined) {
          return (
            <span>
              <ValueWithUnit value={u.lower} digits={2} />
              {' – '}
              <ValueWithUnit value={u.upper} digits={2} />
            </span>
          );
        }
        return <span className="text-ink-2">{t('validation.noUncertainty')}</span>;
      },
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Plainly as text, before any table. A reader who never looks at the grid
          still leaves with the three numbers the paper is cited for. */}
      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.plainTitle')}</h3>
        <dl className="m-0 flex flex-col gap-2 text-xs">
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.plainSalinity')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.salinity_anomaly.value}
                unit={record.salinity_anomaly.unit}
                digits={2}
                provenance={record.salinity_anomaly.provenance}
              />
            </dd>
          </div>
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.plainTurbidity')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.peak_suspended_sediment.value}
                unit={record.peak_suspended_sediment.unit}
                digits={2}
                provenance={record.peak_suspended_sediment.provenance}
              />
            </dd>
          </div>
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.plainDuration')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.elevated_duration_hours.value}
                unit={record.elevated_duration_hours.unit}
                digits={2}
                provenance={record.elevated_duration_hours.provenance}
              />
            </dd>
          </div>
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.plainMass')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.sediment_mass_total.value}
                unit={record.sediment_mass_total.unit}
                digits={0}
                provenance={record.sediment_mass_total.provenance}
              />
            </dd>
          </div>
        </dl>
      </Card>

      {/* The same five quantities with their provenance tag and uncertainty
          rendered rather than dropped. A reported number, a converted number and
          a derived one are three different claims. */}
      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.fieldsTitle')}</h3>
        <DataTable
          columns={fieldColumns}
          rows={FIELDS}
          getRowKey={(key) => key}
          ariaLabel={t('validation.fieldsTitle')}
        />
        {!record.series_available ? (
          // Flagged explicitly, not styled away: the raw 5-minute trace is not
          // served by the API, so a time-series line chart cannot be drawn from
          // real data — and we do not draw one from invented data.
          <div className="flex items-start gap-2 rule bg-surface-2 p-3 text-2xs text-ink-2">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-px shrink-0 text-accent">
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 7.2v3.6" />
              <circle cx="8" cy="4.9" r="0.5" fill="currentColor" />
            </svg>
            <span className="max-w-prose">{t('validation.seriesUnavailable')}</span>
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.markersTitle')}</h3>
        {/* A real timeline of the measured markers over time, dot colour driven
            by provenance form (measured vs modelled), not a plain list. */}
        <Timeline
          ariaLabel={t('validation.markersTitle')}
          entries={record.markers.map((m) => ({
            key: m.key,
            label: t(`validation.marker.${m.key}`),
            time: m.t,
            meta: t(`common:provenance.${m.provenance}`),
            provenance: m.provenance,
          }))}
        />
        <p className="m-0 text-2xs text-ink-3">{t('validation.markersNote')}</p>
      </Card>

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.positionTitle')}</h3>
        <dl className="m-0 flex flex-wrap gap-x-6 gap-y-2 text-xs">
          <div className="flex items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.lon')}</dt>
            <dd className="m-0">
              <ValueWithUnit value={record.position.lon} digits={5} provenance="converted" />
            </dd>
          </div>
          <div className="flex items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.lat')}</dt>
            <dd className="m-0">
              <ValueWithUnit value={record.position.lat} digits={5} provenance="converted" />
            </dd>
          </div>
          <div className="flex items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.depth')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.position.depth_m}
                unit="m"
                digits={0}
                provenance="reported"
              />
            </dd>
          </div>
          <div className="flex items-baseline gap-2">
            <dt className="text-ink-2">{t('validation.positionRadius')}</dt>
            <dd className="m-0">
              <ValueWithUnit
                value={record.position.uncertainty_radius_m}
                unit="m"
                digits={0}
                provenance="converted"
              />
            </dd>
          </div>
        </dl>
        {record.position.note ? (
          <p dir="ltr" className="m-0 max-w-prose text-2xs text-ink-2">
            {record.position.note}
          </p>
        ) : null}
      </Card>

      {record.caveats.length ? (
        <Card>
          <h3 className="m-0 text-sm font-semibold">{t('validation.caveatsTitle')}</h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0 text-xs">
            {record.caveats.map((c) => (
              <li key={`${c.field}:${c.message.slice(0, 24)}`} className="flex flex-col gap-0.5">
                <span dir="auto" className="max-w-prose text-ink-2">
                  {c.message}
                </span>
                {c.source ? (
                  <code dir="ltr" className="font-mono num text-2xs text-ink-3">
                    {c.source}
                  </code>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.targetTitle')}</h3>
        <p dir="ltr" className="m-0 max-w-prose text-xs text-ink-2">
          {record.source_citation}
        </p>
        <p className="m-0 text-2xs text-ink-3">
          <code dir="ltr" className="font-mono num">
            doi:{record.source_doi}
          </code>
        </p>
        <p className="m-0 text-2xs text-ink-3">
          {t('validation.source')}{' '}
          <code dir="ltr" className="font-mono num">
            {record.source_file}
          </code>
        </p>
      </Card>
    </div>
  );
}
