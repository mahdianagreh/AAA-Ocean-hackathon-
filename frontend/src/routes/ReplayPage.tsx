import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import { loadEventSeries, type EventSeries } from '../api/event';
import {
  fetchExposure,
  fetchPlumeFrames,
  fetchRunoffPredict,
  type ExposureRun,
  type PlumeFrames,
  type RunoffPrediction,
} from '../api/live';
import { bandForSeverity } from '../api/predictions';
import { DEMO_OUTLET } from '../api/types';
import { CaveatList } from '../components/CaveatList';
import { Link } from '../components/Link';
import { Empty, ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';
import { BandChip, Caveats, IdText } from './AlertsPage';

/** Historical replay, at /dashboard/replay/:eventId — the full chain, in order:
 *  rainfall → runoff → sediment → plume → exposure, each from a real endpoint.
 *
 *  The chain does not fail uniformly. Rainfall (a build-time fixture keyed to
 *  the anchor event only) and the plume/exposure pair (needs a real
 *  `flood_arrival_utc`) are anchor-only. Runoff and sediment are NOT: Component
 *  A/B score any event with a real row in `training_set_full.parquet`, no
 *  flood-arrival dependency — so a non-anchor event shows a genuinely partial
 *  chain (runoff/sediment real, rainfall/plume/exposure absent-and-stated)
 *  rather than nothing at all. Rendering that distinction honestly is the point
 *  of keeping the stages separate rather than gating the whole page on one flag.
 *
 *  The plume engine itself is real — `plume_source` comes back
 *  `particle-engine`, not `stub`. Two things about its forcing are not fully
 *  real, and both are rendered from `plume.provenance`/`plume.caveats`
 *  verbatim rather than asserted as fixed prose: which one is true (real cached
 *  HYCOM currents vs. the documented placeholder) depends on whether
 *  `data/raw/currents/` happens to hold the archive on a given checkout, so a
 *  hardcoded claim would be wrong exactly when the archive IS cached — which is
 *  what this project's own Phase 7 baseline check found here. Wind is the one
 *  unconditional part: `ConstantWindField(0, 0)`, no historical marine wind
 *  source exists in this project at all.
 *
 *  The exposure run for the anchor event currently returns NO results, and its
 *  own caveat says why: the nearest reef zone is 1923 m from AQ-O01 and the
 *  plume's largest modelled extent is 418 m. "Not reached" is rendered as not
 *  reached, never as zero-risk exposure.
 *
 *  The anchor event id is read from the committed event fixture rather than
 *  typed in, because no event date is hard-coded anywhere in this project.
 */

const STEP_MS_HINT = 5; // seconds, documented in the copy — frames render server-side

// AQ-O01 <-> AQ-C01 is fixed, settled geometry (CLAUDE.md's ID contract: 5
// catchments, 5 outlets, never renamed) — not a computation, so not worth a
// second network fetch of basemap geometry on a page that has no other reason
// to load it. If DEMO_OUTLET ever changes, this must change with it.
const CATCHMENT_FOR_OUTLET: Record<string, string> = { 'AQ-O01': 'AQ-C01' };

export function ReplayPage({ eventId }: { eventId?: string }) {
  const { t } = useTranslation('pages');

  const [anchorId, setAnchorId] = useState<string | null>(null);
  const [anchorSeries, setAnchorSeries] = useState<EventSeries | null>(null);
  const [anchorResolved, setAnchorResolved] = useState(false);
  const [plume, setPlume] = useState<PlumeFrames | null>(null);
  const [exposure, setExposure] = useState<ExposureRun | null>(null);
  const [runoff, setRunoff] = useState<RunoffPrediction | null>(null);
  const [runoffLoaded, setRunoffLoaded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // `step` is the frame the last click asked for; `shownStep` is the frame whose
  // image has actually decoded. They diverge for as long as the server takes to
  // render the next one — measured at ~5 s — and without the split the old frame
  // sits there through that gap and the click looks like it did nothing. Same
  // approach as PlumeMapPanel, which this page deliberately mirrors.
  const [step, setStep] = useState(0);
  const [shownStep, setShownStep] = useState(0);
  const requested = useRef(0);

  useEffect(() => {
    let live = true;
    void loadEventSeries()
      .then((s) => {
        if (!live) return;
        setAnchorId(s.event_id);
        setAnchorSeries(s);
      })
      .catch(() => {
        // The fixture is bundled, so this only fails if the build is broken.
        // Either way the page must not hang on it.
      })
      .finally(() => {
        if (live) setAnchorResolved(true);
      });
    return () => {
      live = false;
    };
  }, []);

  const effectiveId = eventId ?? anchorId;
  const catchmentId = CATCHMENT_FOR_OUTLET[DEMO_OUTLET];

  useEffect(() => {
    if (!effectiveId) return;
    let live = true;
    setLoaded(false);
    setPlume(null);
    setExposure(null);
    setStep(0);
    setShownStep(0);

    void Promise.all([fetchPlumeFrames(effectiveId), fetchExposure(effectiveId)]).then(
      ([p, e]) => {
        if (!live) return;
        setPlume(p);
        setExposure(e);
        setLoaded(true);
      },
    );

    return () => {
      live = false;
    };
  }, [effectiveId]);

  // Runoff/sediment (Component A/B) has no flood-arrival dependency, unlike
  // plume/exposure — it resolves for any event with a real feature row, so it
  // is fetched independently rather than gated on the anchor-only Promise.all
  // above. A non-anchor event can legitimately show real runoff/sediment next
  // to an absent-and-stated plume/exposure; that partial chain is more honest
  // than hiding what DID compute because something else on the page did not.
  useEffect(() => {
    if (!effectiveId) return;
    let live = true;
    setRunoffLoaded(false);
    setRunoff(null);
    void fetchRunoffPredict(effectiveId, catchmentId).then((r) => {
      if (!live) return;
      setRunoff(r);
      setRunoffLoaded(true);
    });
    return () => {
      live = false;
    };
  }, [effectiveId, catchmentId]);

  // The flood-day rainfall depth for this catchment, from the anchor's own
  // committed series — the only rainfall source in this project, and it is
  // keyed to the anchor event alone (docs/event_dates.md's converted arrival
  // times exist only for AQ-2016-10-28). Showing it under a non-anchor id
  // would silently attribute Oct 2016's rainfall to a different storm, so it
  // renders only when `isAnchor` — see the render below.
  const floodDayRainfall = useMemo(() => {
    if (!anchorSeries || !anchorId) return null;
    const datePart = anchorId.slice(3); // 'AQ-2016-10-28' -> '2016-10-28'
    const series = anchorSeries.rainfall_daily.by_catchment[catchmentId] ?? [];
    return series.find((p) => p.t.startsWith(datePart)) ?? null;
  }, [anchorSeries, anchorId, catchmentId]);

  const frames = useMemo(() => plume?.frames ?? [], [plume]);

  useEffect(() => {
    if (frames.length === 0) return;
    const target = frames[Math.min(step, frames.length - 1)];
    requested.current = step;
    const img = new Image();
    img.onload = () => {
      // A slow earlier frame resolving after a faster later one must not roll
      // the view backward.
      if (requested.current === step) setShownStep(step);
    };
    img.src = `${API_BASE}${target.url}`;
  }, [step, frames]);

  const isAnchor = effectiveId !== null && effectiveId === anchorId;
  const results = exposure?.results ?? [];
  const runCaveats = exposure?.caveats ?? [];

  if (!anchorResolved || !effectiveId) {
    return (
      <PageShell title={t('replay.title')}>
        {anchorResolved && !effectiveId ? (
          <ErrorState what={t('replay.noEventTitle')} message={t('replay.noEventBody')} />
        ) : (
          <Loading what={t('replay.loading')} />
        )}
      </PageShell>
    );
  }

  return (
    <PageShell
      title={t('replay.title')}
      lede={
        <span className="flex flex-wrap items-baseline gap-2">
          <IdText>{effectiveId}</IdText>
          <span>·</span>
          <IdText>{DEMO_OUTLET}</IdText>
          {eventId ? null : <span>{t('replay.defaultedToAnchor')}</span>}
        </span>
      }
      actions={
        <Link to="/events" className="text-xs underline">
          {t('replay.backToEvents')}
        </Link>
      }
    >
      <Section label={t('replay.rainfallLabel')}>
        {!isAnchor ? (
          <Empty title={t('replay.rainfallUnavailableTitle')} body={t('replay.rainfallUnavailableBody')} />
        ) : !anchorResolved ? (
          <Loading what={t('replay.loading')} />
        ) : floodDayRainfall === null ? (
          <Empty title={t('replay.rainfallUnavailableTitle')} body={t('replay.rainfallUnavailableBody')} />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline gap-4">
              <span className="flex flex-col gap-0.5">
                <ValueWithUnit
                  value={floodDayRainfall.mm}
                  unit={anchorSeries?.rainfall_daily.unit}
                  digits={2}
                  provenance={anchorSeries?.rainfall_daily.provenance}
                />
                <span className="text-2xs text-ink-3">
                  {t('replay.rainfallFloodDay', { catchment: catchmentId })}
                </span>
              </span>
            </div>
            <p className="m-0 max-w-prose text-2xs text-ink-2">{anchorSeries?.rainfall_daily.note}</p>
            <p className="m-0 text-2xs text-ink-3">
              {t('replay.source')}{' '}
              <IdText>{anchorSeries?.rainfall_daily.source ?? ''}</IdText>
            </p>
          </div>
        )}
      </Section>

      <Section label={t('replay.runoffSedimentLabel')}>
        {!runoffLoaded ? (
          <Loading what={t('replay.loading')} />
        ) : runoff === null ? (
          <ErrorState what={t('replay.runoffUnavailableTitle')} message={t('replay.runoffUnavailableBody')} />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-6">
              <span className="flex flex-col gap-0.5">
                <ValueWithUnit value={runoff.runoff_probability} digits={2} provenance="modelled" />
                <span className="text-2xs text-ink-3">{t('replay.runoffProbability')}</span>
              </span>
              <span className="flex flex-col gap-0.5">
                {runoff.severity ? (
                  <BandChip band={bandForSeverity(runoff.severity)} />
                ) : (
                  <ValueWithUnit value={null} />
                )}
                <span className="text-2xs text-ink-3">{t('replay.runoffSeverity')}</span>
              </span>
              <span className="flex flex-col gap-0.5">
                <ValueWithUnit value={runoff.relative_sediment_intensity} digits={3} provenance="modelled" />
                <span className="text-2xs text-ink-3">{t('replay.sedimentIntensity')}</span>
              </span>
              <span className="flex flex-col gap-0.5">
                {runoff.sediment_class ? (
                  <span className="text-sm font-semibold text-ink">
                    {t(`replay.sedimentClassValue.${runoff.sediment_class}`)}
                  </span>
                ) : (
                  <ValueWithUnit value={null} />
                )}
                <span className="text-2xs text-ink-3">{t('replay.sedimentClass')}</span>
              </span>
            </div>

            {runoff.drivers.length > 0 ? (
              <div className="flex flex-col gap-1">
                <p className="m-0 text-2xs font-semibold text-ink-2">{t('common:risk.drivers')}</p>
                <ul className="m-0 flex flex-col gap-1 p-0 text-2xs text-ink-2">
                  {runoff.drivers.map((d) => (
                    <li key={d.key} className="flex items-baseline justify-between gap-2">
                      <span>{t(`common:driver.${d.key}`, { defaultValue: d.key })}</span>
                      <ValueWithUnit value={d.contribution} digits={3} provenance="modelled" />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <p className="m-0 text-2xs text-ink-3">
              {t('replay.modelVersions')} <IdText>{runoff.model_version}</IdText>
            </p>

            <CaveatList items={runoff.caveats} />
          </div>
        )}
      </Section>

      <Section label={t('replay.playbackLabel')}>
        {!loaded ? (
          <Loading what={t('replay.simulating', { seconds: STEP_MS_HINT })} />
        ) : frames.length === 0 ? (
          // The whole point of this branch: no frames means no simulation, and
          // the reason is different for the anchor event than for any other.
          isAnchor ? (
            <ErrorState what={t('replay.anchorFailedTitle')} message={t('replay.anchorFailedBody')} />
          ) : (
            <Empty title={t('replay.onlyAnchorTitle')} body={t('replay.onlyAnchorBody')} />
          )
        ) : (
          <>
          <div className="glass-card p-6 flex flex-col gap-5 mt-4">
            <div className="flex flex-wrap items-baseline gap-4">
              <p className="m-0 text-xs font-medium text-ink-2">
                {t('replay.plumeSource')} <IdText className="bg-surface/50 px-1 rounded text-accent">{plume?.plume_source ?? ''}</IdText>
              </p>
              <p className="m-0 text-xs font-medium text-ink-2">
                {t('replay.frameCount')}{' '}
                <ValueWithUnit value={frames.length} digits={0} provenance="modelled" />
              </p>
              <p className="m-0 text-xs font-medium text-ink-2">
                {t('replay.basemap')}{' '}
                {plume?.basemap_present ? t('replay.basemapReal') : t('replay.basemapAbsent')}
              </p>
            </div>

            <img
              src={`${API_BASE}${frames[Math.min(shownStep, frames.length - 1)].url}`}
              alt={t('replay.frameAlt', {
                hours: frames[Math.min(shownStep, frames.length - 1)].t_hours,
                event: effectiveId,
              })}
              aria-busy={step !== shownStep}
              className={`w-full rounded-xl shadow-2xl border border-hairline-2 transition-opacity ${
                step !== shownStep ? 'opacity-50' : ''
              }`}
            />
            {step !== shownStep ? (
              <p aria-live="polite" className="m-0 text-2xs text-ink-3">
                {t('replay.rendering', { seconds: STEP_MS_HINT })}
              </p>
            ) : null}

            <div
              className="flex items-center gap-2 overflow-x-auto pb-2"
              role="group"
              aria-label={t('replay.stepper')}
            >
              {frames.map((f, i) => (
                <button
                  key={f.t_hours}
                  type="button"
                  onClick={() => setStep(i)}
                  aria-pressed={i === step}
                  className={`min-h-8 shrink-0 rounded-full px-4 py-1.5 font-mono num text-sm font-bold transition-all duration-300 cursor-pointer ${
                    i === step ? 'premium-button text-surface scale-105 shadow-[0_0_15px_var(--accent)]' : 'glass-panel text-ink-2 hover:scale-105 hover:neon-glow hover:border-accent'
                  }`}
                >
                  {`+${f.t_hours} ${t('units.hours')}`}
                </button>
              ))}
            </div>
          </div>

            {/* Not a footnote. A direction read off these frames is a direction
                nothing forced. Rendered from `plume.provenance`/`caveats`
                verbatim rather than a fixed sentence — see the module docstring
                on why a hardcoded "falls back to zero" claim is wrong exactly
                when the HYCOM archive is cached for this event. */}
            <div className="flex flex-col gap-2 glass-panel p-5 mt-4 group">
              <p className="m-0 text-base font-bold premium-gradient-text">{t('replay.forcingTitle')}</p>
              {(plume?.provenance ?? []).map((p, i) => (
                <p key={`${p.kind}-${i}`} className="m-0 max-w-prose text-sm text-ink-2 leading-relaxed">
                  {p.detail}
                </p>
              ))}
              <p className="m-0 max-w-prose text-sm text-ink-2 leading-relaxed">
                {t('replay.forcingWindStatement')}
              </p>
              {plume?.windage_is_tiebreak && plume.windage_caveat ? (
                <p className="m-0 max-w-prose text-sm text-ink-2 leading-relaxed">{plume.windage_caveat}</p>
              ) : null}
              <p className="m-0 max-w-prose text-sm text-ink-2 leading-relaxed">
                {t('replay.forcingDiffusionBody')}
              </p>
            </div>

            <CaveatList items={plume?.caveats ?? []} />
          </>
        )}
      </Section>

      <Section label={t('replay.exposureLabel')}>
        {!loaded ? (
          <Loading what={t('replay.loadingExposure')} />
        ) : exposure === null ? (
          <Empty title={t('replay.noExposureRunTitle')} body={t('replay.noExposureRunBody')} />
        ) : results.length === 0 ? (
          <Empty title={t('replay.noZoneReachedTitle')} body={t('replay.noZoneReachedBody')} />
        ) : (
          <div className="overflow-x-auto glass-panel p-5 mt-4">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">{t('replay.tableCaption')}</caption>
              <thead>
                <tr className="border-b border-hairline-2 text-xs text-ink-2 font-bold premium-gradient-text">
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.zone')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.band')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.score')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.probability')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.fraction')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.window')}
                  </th>
                  <th scope="col" className="p-3 text-start">
                    {t('replay.col.confidence')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.reef_zone_id} className="border-b border-hairline align-top transition-colors hover:bg-surface/50 group/row">
                    <th scope="row" className="p-3 text-start font-medium group-hover/row:text-accent transition-colors">
                      <Link to={`/reef-zones/${encodeURIComponent(r.reef_zone_id)}`} className="underline">
                        <IdText>{r.reef_zone_id}</IdText>
                      </Link>
                    </th>
                    <td className="p-3">
                      <BandChip band={r.risk_level} />
                    </td>
                    <td className="p-3">
                      <ValueWithUnit value={r.risk_score} digits={1} provenance="modelled" />
                    </td>
                    <td className="p-3">
                      <ValueWithUnit
                        value={r.max_exposure_probability}
                        digits={2}
                        provenance="modelled"
                      />
                    </td>
                    <td className="p-3">
                      {/* Share of THIS zone, never a bare km²: the zones differ
                          in area by an order of magnitude, so an absolute area
                          affected reads as a comparison it cannot support. */}
                      <ValueWithUnit
                        value={r.zone_fraction_affected * 100}
                        digits={1}
                        unit={t('units.pct')}
                        provenance="modelled"
                      />
                      <span className="block text-xs text-ink-3 mt-1">
                        {t('replay.fractionOf', { zone: r.reef_zone_id })}
                      </span>
                    </td>
                    <td className="p-3">
                      {r.arrival_window_hours ? (
                        <span className="inline-flex items-baseline gap-1">
                          <ValueWithUnit
                            value={r.arrival_window_hours[0]}
                            digits={0}
                            provenance="modelled"
                          />
                          <span aria-hidden="true">–</span>
                          <ValueWithUnit
                            value={r.arrival_window_hours[1]}
                            digits={0}
                            unit={t('units.hours')}
                            provenance="modelled"
                          />
                        </span>
                      ) : (
                        <ValueWithUnit value={null} />
                      )}
                    </td>
                    <td className="p-3">{t(`replay.confidenceValue.${r.confidence}`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {exposure ? (
        <Section label={t('replay.provenanceLabel')}>
          <div className="glass-panel p-5 mt-4">
            <h3 className="m-0 text-base font-bold text-ink">{t('replay.modelVersions')}</h3>
            <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 mt-2 text-xs">
              {Object.entries(exposure.model_versions).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-ink-2">
                    <IdText>{k}</IdText>
                  </dt>
                  <dd className="m-0">
                    <IdText className="bg-surface/50 px-1 rounded text-accent">{v}</IdText>
                  </dd>
                </div>
              ))}
            </dl>
            <p className="m-0 text-xs text-ink-3 mt-4">
              {t('replay.runId')} <IdText>{exposure.run_id}</IdText>
            </p>
          </div>
        </Section>
      ) : null}

      {runCaveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <Caveats items={runCaveats} />
        </Section>
      ) : null}
    </PageShell>
  );
}
