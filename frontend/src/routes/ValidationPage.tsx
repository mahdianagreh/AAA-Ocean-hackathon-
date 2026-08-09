import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { ValueWithUnit } from '../components/ValueWithUnit';
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
            <table className="w-full border-collapse text-xs">
              <caption className="sr-only">{t('validation.calibrationTitle')}</caption>
              <thead>
                <tr className="border-b border-hairline-2 text-xs premium-gradient-text pb-2">
                  <th scope="col" className="py-2 text-start font-bold">
                    {t('validation.quantity')}
                  </th>
                  <th scope="col" className="py-2 text-end font-bold">
                    {t('validation.error')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ['arrival', record.calibration_fit.arrival_time_error_hours],
                    ['duration', record.calibration_fit.duration_error_hours],
                    ['peak', record.calibration_fit.peak_timing_error_hours],
                  ] as const
                ).map(([key, value]) => (
                  <tr key={key} className="border-b border-hairline hover:bg-surface/50 transition-colors group/row cursor-default">
                    <th scope="row" className="py-2 text-start font-normal text-ink-2 group-hover/row:text-accent transition-colors">
                      {t(`validation.calibration.${key}`)}
                    </th>
                    <td className="py-1 text-end">
                      <ValueWithUnit value={value} unit="h" digits={2} provenance="modelled" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t('validation.fieldsTitle')}>
          <table className="w-full border-collapse text-xs">
            <caption className="sr-only">{t('validation.fieldsTitle')}</caption>
            <thead>
              <tr className="border-b border-hairline-2 text-xs premium-gradient-text pb-2">
                <th scope="col" className="py-2 pe-3 text-start font-bold">
                  {t('validation.quantity')}
                </th>
                <th scope="col" className="py-2 pe-3 text-end font-bold">
                  {t('validation.measured')}
                </th>
                <th scope="col" className="py-2 pe-3 text-start font-bold">
                  {t('validation.provenanceLabel')}
                </th>
                <th scope="col" className="py-2 text-start font-bold">
                  {t('validation.uncertaintyLabel')}
                </th>
              </tr>
            </thead>
            <tbody>
              {FIELDS.map((key) => {
                const v = record[key];
                return (
                  <tr key={key} className="border-b border-hairline hover:bg-surface/50 transition-colors group/row cursor-default">
                    <th scope="row" className="py-2 pe-3 text-start font-normal text-ink-2 group-hover/row:text-accent transition-colors">
                      {t(`validation.field.${key}`)}
                    </th>
                    <td className="py-1 pe-3 text-end">
                      <ValueWithUnit
                        value={v.value}
                        unit={v.unit}
                        digits={DIGITS[key]}
                        provenance={v.provenance}
                      />
                    </td>
                    <td className="py-1 pe-3 text-ink-2">
                      {t(`common:provenance.${v.provenance}`)}
                    </td>
                    <td className="py-1 text-ink-2">
                      {v.uncertainty?.sigma !== undefined && v.uncertainty.sigma !== null ? (
                        <span>
                          {t('validation.sigma')}{' '}
                          <ValueWithUnit value={v.uncertainty.sigma} digits={0} />
                        </span>
                      ) : v.uncertainty?.lower !== undefined && v.uncertainty.upper !== undefined ? (
                        <span>
                          <ValueWithUnit value={v.uncertainty.lower} digits={2} />
                          {' – '}
                          <ValueWithUnit value={v.uncertainty.upper} digits={2} />
                        </span>
                      ) : (
                        <span className="text-ink-3">{t('validation.noUncertainty')}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!record.series_available ? (
          <p className="m-0 text-2xs text-ink-3">{t('validation.seriesUnavailable')}</p>
        ) : null}
      </Card>

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('validation.markersTitle')}</h3>
        <dl className="m-0 flex flex-col gap-1 text-xs">
          {record.markers.map((m) => (
            <div key={m.key} className="flex flex-wrap items-baseline gap-2">
              <dt className="text-ink-2">{t(`validation.marker.${m.key}`)}</dt>
              <dd className="m-0 flex flex-wrap items-baseline gap-2">
                <code dir="ltr" className="font-mono num">
                  {m.t}
                </code>
                <span className="text-2xs text-ink-3">
                  {t(`common:provenance.${m.provenance}`)}
                </span>
              </dd>
            </div>
          ))}
        </dl>
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
