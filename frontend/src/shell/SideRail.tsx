import { useTranslation } from 'react-i18next';
import { useUi } from '../app/uiStore';
import type { EventData } from '../app/useEventData';
import type { LiveExposure } from '../app/useLiveExposure';
import type { RiskCardData } from '../components/RiskCard';
import { RiskCard } from '../components/RiskCard';
import { Hyetograph } from '../components/Hyetograph';
import { SubDailyWindows } from '../components/SubDailyWindows';
import { Legend } from '../components/Legend';
import { LayerToggle } from '../components/LayerToggle';
import { ScenarioDrawer } from '../components/ScenarioDrawer';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PlumeMapPanel } from '../components/PlumeMapPanel';
import { ForecastPanel } from '../panels/ForecastPanel';
import { HARBOUR_BASIN_OUTLETS } from '../api/types';
import type { HazardBand, Outlet } from '../api/types';
import { BAND_CLASS, HAZARD_RANGES } from '../api/types';

/** p4-D: appends the real culvert numbers behind AQ-O02/AQ-O03's map flag, so
 *  the tooltip a reader gets here says the same thing the coloured dot does —
 *  never a per-culvert count implying a dataset `/outlets` cannot serve (there
 *  is no per-culvert endpoint), only this outlet's own aggregate fields.
 *  `nearest_culvert_m` is already computed in EPSG:32636 server-side; this
 *  never re-derives a distance from `lon`/`lat`, which is exactly the mistake
 *  that once overstated every culvert distance by 14.8% (measuring in
 *  degrees/Web Mercator instead of UTM 36N). */
function culvertCaveat(o: Outlet): string {
  if (!o.culvert_verdict?.includes('CANDIDATE CORRECTION')) return o.caveat;
  const nearest =
    o.nearest_culvert_m != null ? `${o.nearest_culvert_m.toFixed(0)} m` : 'an unknown distance';
  const unmodelled = o.unmodelled_coastal_culverts ?? 0;
  return (
    `${o.caveat} ${o.culvert_verdict}: nearest real culvert ${nearest} away ` +
    `(EPSG:32636), ${unmodelled} unmodelled coastal culvert${unmodelled === 1 ? '' : 's'} nearby.`
  );
}

/** Side rail: risk cards, layer toggles, legend — 03 §3.
 *
 *  Also the textual equivalent of the map (09 rule 7 / 01 §6.5), which is why the
 *  values live here rather than only in tooltips. Everything reads the cursor from
 *  the store, so scrubbing moves the cards and the chart with the map.
 *
 *  03 §5 asked whether risk cards show all zones or only those above `low`. Answer:
 *  all of them, sorted by score. With five catchments the list is short, and hiding
 *  the quiet ones would make "nothing is happening" indistinguishable from "the
 *  layer failed to load" — which is the empty state 03 §2 calls a first-class
 *  design problem, not a fallback.
 */
export function SideRail({
  data,
  risk,
  error,
  live,
}: {
  data: EventData | null;
  risk: RiskCardData[];
  error: string | null;
  live: LiveExposure;
}) {
  const { t } = useTranslation();
  const { mode, cursor, setCursor, layers, toggleLayer } = useUi();

  // Forecast mode's real content lives here, not the historical scene below —
  // tasks/phase7/03-nizar.md's decision: show what /forecast/latest actually
  // has, never silently fall back to the historical training-row path.
  if (mode === 'forecast') {
    return (
      <aside
        className="flex min-h-0 flex-col gap-5 overflow-y-auto bg-surface p-4"
        aria-label={t('rail.label')}
      >
        <ForecastPanel active />
      </aside>
    );
  }

  const ranked = [...risk].sort((a, b) => b.score - a.score);
  const worst = ranked[0];

  // Joined by reef_zone_id, not assumed to be in the same order — the API
  // returns exposure results in whatever order the engine iterated the zones,
  // and the rail lists all eight regardless of whether a live run exists.
  const exposureByZone = new Map(live.exposure?.results.map((r) => [r.reef_zone_id, r]) ?? []);

  return (
    <aside
      className="flex min-h-0 flex-col gap-5 overflow-y-auto bg-surface p-4"
      aria-label={t('rail.label')}
    >
      {error ? (
        <p role="alert" className="text-xs text-risk-critical">
          {error}
        </p>
      ) : null}

      {!data && !error ? <p className="text-xs text-ink-3">{t('rail.loading')}</p> : null}

      {data ? (
        <>
          {/* Scene 3: rainfall and the activated catchment. The chart leads
              because the officer's first question is what fell and where. */}
          <Hyetograph
            byCatchment={data.series.rainfall_daily.by_catchment}
            unit={data.series.rainfall_daily.unit}
            cursor={cursor}
            onCursor={setCursor}
            marks={data.series.mooring.markers.map((m) => ({
              t: m.t,
              label: t(`mooring.${m.key}`),
            }))}
          />

          {/* The heaviest sub-daily totals, as the honest scalar extrema they are —
              never a rolling series the repo does not have (p4-16). */}
          <SubDailyWindows subdaily={data.series.subdaily} />

          {/* Scene 8: the recommendation. One card leads — the worst catchment at
              this step — and the rest follow, because there is one decision to
              make and four pieces of context. */}
          <section className="flex flex-col gap-2">
            <h2 className="flex items-baseline justify-between border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.risk')}
              {worst ? (
                <span className="font-normal text-ink-3">
                  {t('rail.worst')}{' '}
                  <span
                    dir="ltr"
                    style={{ unicodeBidi: 'isolate' }}
                    className="font-mono num text-2xs"
                  >
                    {worst.catchment_id}
                  </span>
                </span>
              ) : null}
            </h2>
            {ranked.map((r) => (
              <RiskCard key={r.catchment_id} data={r} />
            ))}
          </section>

          {/* Scene 6's inputs, and the reason the whole project pivoted here: the
              satellite route is a null result, so the mooring record is the
              validation target. Measured values, so they are solid-form. */}
          <section className="flex flex-col gap-1">
            <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.mooring')}
            </h2>
            <Row label={t('mooring.peakSediment')}>
              <ValueWithUnit
                value={data.series.mooring.peak_suspended_sediment.value}
                unit={data.series.mooring.peak_suspended_sediment.unit}
                digits={2}
                provenance="reported"
              />
            </Row>
            <Row label={t('mooring.salinityAnomaly')}>
              <ValueWithUnit
                value={data.series.mooring.salinity_anomaly.value}
                unit={data.series.mooring.salinity_anomaly.unit}
                digits={2}
                provenance="reported"
              />
            </Row>
            <Row label={t('mooring.elevatedDuration')}>
              <ValueWithUnit
                value={data.series.mooring.elevated_duration_hours.value}
                unit={data.series.mooring.elevated_duration_hours.unit}
                digits={2}
                provenance="converted"
              />
            </Row>
            <Row label={t('mooring.sedimentMass')}>
              <ValueWithUnit
                value={data.series.mooring.sediment_mass_total.value}
                unit={data.series.mooring.sediment_mass_total.unit}
                digits={0}
                provenance="reported"
              />
            </Row>
            <p className="text-2xs text-ink-3">{t('mooring.noSeries')}</p>
          </section>

          {/* Outlets, with AQ-O04's caveat travelling with it — 01 §6.7.
              p4-D: the map flags AQ-O02/AQ-O03 with a coloured dot and a label;
              09 rule 7 requires the same fact reach a reader who never looks at
              the map, with the real numbers behind it, not just a repeated
              badge. */}
          <section className="flex flex-col gap-1">
            <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.outlets')}
            </h2>
            {data.outlets.map((o) => (
              <Row
                key={o.outlet_id}
                label={o.outlet_id}
                caveat={culvertCaveat(o)}
                warn={
                  HARBOUR_BASIN_OUTLETS.has(o.outlet_id) ||
                  Boolean(o.culvert_verdict?.includes('CANDIDATE CORRECTION'))
                }
              >
                <ValueWithUnit
                  value={o.upstream_km2 ?? null}
                  unit="km²"
                  digits={0}
                  provenance="modelled"
                />
              </Row>
            ))}
          </section>

          {/* Reef zones by name. 09 rule 7: the map is never the only path to a
              fact, and these are the subject of the product — the map draws eight
              polygons, so the rail has to name eight zones. An earlier version of
              this rail dropped them in favour of the legend alone, and the offline
              test caught it as a missing R-01. Phase 3's exposure scores land in
              this same list. */}
          <section className="flex flex-col gap-1">
            <h2 className="flex items-baseline justify-between border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.reefZones')}
              {/* States.tsx's vocabulary: loading vs a stated absence, not the
                  same blank for both — this call has no fixture fallback. */}
              {live.loading ? (
                <span className="font-normal text-ink-3">{t('rail.loading')}</span>
              ) : null}
            </h2>
            {data.reef.map((r) => {
              const exposure = exposureByZone.get(r.reef_zone_id);
              return (
                <Row
                  key={r.reef_zone_id}
                  label={r.reef_zone_id}
                  // The habitat class is real information now that the ACA swap has
                  // landed; the provisional file said 'unknown' for all eight.
                  caveat={[r.zone_name, r.habitat_class, r.geomorphic_class]
                    .filter(Boolean)
                    .join(' · ')}
                >
                  <span className="flex items-baseline gap-2">
                    <span dir="auto" className="max-w-40 truncate text-2xs text-ink-3">
                      {r.habitat_class ?? r.zone_name}
                    </span>
                    <ValueWithUnit value={r.area_km2} unit="km²" digits={2} provenance="modelled" />
                    {/* Only shown once a run exists — a stub-flat 'minimal' for
                        every zone before Abd's real plume lands is a fact about
                        the plume being synthetic, not about these reefs, and
                        rendering it unlabelled would be exactly the overclaim
                        09 rule 8 forbids. */}
                    {exposure ? (
                      <span
                        data-band={exposure.risk_level}
                        title={t('rail.exposureTitle', {
                          score: exposure.risk_score.toFixed(0),
                          range: HAZARD_RANGES[exposure.risk_level as HazardBand],
                        })}
                        className={`border px-1 text-2xs ${BAND_CLASS[exposure.risk_level as HazardBand]}`}
                      >
                        {t(`hazard.${exposure.risk_level}`)}
                      </span>
                    ) : null}
                  </span>
                </Row>
              );
            })}
            {live.exposure ? (
              <p className="text-2xs text-ink-3">
                {t('rail.exposureNote', {
                  sediment: (
                    live.exposure.results[0]?.formula_terms.relative_sediment_intensity ?? 0
                  ).toFixed(3),
                })}
              </p>
            ) : null}
          </section>

          {/* Real stored alerts, or the stated absence — never a spinner or a
              silent gap where a list should be. `min_level=minimal` is asked for
              explicitly (see api/live.ts): while the plume is a stub every zone
              is capped inside the minimal band, and the default filter on the
              API excludes it, which would otherwise look identical to "the feed
              is broken". */}
          <section className="flex flex-col gap-1">
            <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.alerts')}
            </h2>
            {live.alerts.length === 0 ? (
              <p className="text-2xs text-ink-3">
                {live.loading
                  ? t('rail.loading')
                  : // Two different absences, not one blank for both. `exposure`
                    // is null only when its own call failed outright — a working
                    // call always returns a run, even a near-zero one — so its
                    // presence is what distinguishes "asked the API, genuinely
                    // nothing to alert on" from "could not reach the API at all".
                    // Conflating them would say something false in the second
                    // case: there is no basis here for "every score is capped",
                    // there is simply no answer.
                    live.exposure
                    ? t('rail.alertsEmpty')
                    : t('rail.liveUnreachable')}
              </p>
            ) : (
              live.alerts.map((a) => (
                <Row key={a.alert_id} label={a.reef_zone_id}>
                  <span
                    dir="auto"
                    data-band={a.risk_level}
                    className={`border px-1 text-2xs ${BAND_CLASS[a.risk_level as HazardBand]}`}
                  >
                    {t(`hazard.${a.risk_level}`)}
                  </span>
                </Row>
              ))
            )}
          </section>

          <PlumeMapPanel plume={live.plume} />

          {/* Scene 7, the what-if. In the rail rather than a separate drawer:
              03 §5 asked whether the drawer blocks the map or pushes it, and the
              answer is neither — the controls belong beside the numbers they
              change, so a judge can watch the bands move while dragging. */}
          <ScenarioDrawer />

          <Legend plumeLevels={[0.1, 0.25, 0.5, 0.75]} />
          <LayerToggle layers={layers} onToggle={toggleLayer} />

          <section className="flex flex-col gap-1">
            <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
              {t('rail.coverage')}
            </h2>
            <p className="text-2xs text-ink-3">{t('rail.coverageNote')}</p>
            <p className="text-2xs text-ink-3">{t('rail.reefProvisional')}</p>
          </section>
        </>
      ) : null}
    </aside>
  );
}

export function Row({
  label,
  caveat,
  warn,
  children,
}: {
  label: string;
  caveat?: string;
  warn?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs" title={caveat}>
      <span className="flex min-w-0 items-baseline gap-2">
        {/* dir="auto", not a fixed direction: these labels can be either script,
            and in an RTL container a Latin name truncated with a fixed direction
            puts the ellipsis at the START — losing the half that identifies it. */}
        <span dir="auto" style={{ unicodeBidi: 'isolate' }} className="truncate text-ink-2">
          {label}
        </span>
        {warn ? (
          <span
            className="shrink-0 border border-risk-high-stroke bg-risk-high px-1 text-2xs text-risk-high-on"
            title={caveat}
          >
            !
          </span>
        ) : null}
      </span>
      {children}
    </div>
  );
}
