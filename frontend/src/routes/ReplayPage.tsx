import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import { loadEventSeries } from '../api/event';
import {
  fetchExposure,
  fetchPlumeFrames,
  type ExposureRun,
  type PlumeFrames,
} from '../api/live';
import { DEMO_OUTLET } from '../api/types';
import { Link } from '../components/Link';
import { Empty, ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';
import { BandChip, Caveats, IdText } from './AlertsPage';

/** Historical replay, at /dashboard/replay/:eventId.
 *
 *  The plume engine behind this is real — `plume_source` comes back
 *  `particle-engine`, not `stub`. Three things about it are not, and all three
 *  are stated on the page rather than in a commit message:
 *
 *   1. Ocean currents fall back to `ConstantCurrentField(0, 0)` on this
 *      checkout, and wind forcing is zero. So the cloud's SHAPE is advection
 *      by nothing plus diffusion — a spreading blob, not a drifting plume. The
 *      timing and the mass are meaningful; a direction read off the image is
 *      not.
 *   2. Only the anchor event simulates at all. Every other event_id answers
 *      HTTP 422: the particle engine needs a real `flood_arrival_utc` from
 *      docs/event_dates.md and refuses to guess one. That refusal is correct
 *      behaviour, so it is reported as a stated limit rather than swallowed
 *      into an empty animation — an empty animation would imply a plume shape
 *      that was never computed.
 *   3. The exposure run for the anchor event currently returns NO results, and
 *      its own caveat says why: the nearest reef zone is 1923 m from AQ-O01 and
 *      the plume's largest modelled extent is 418 m. "Not reached" is rendered
 *      as not reached, never as zero-risk exposure.
 *
 *  The anchor event id is read from the committed event fixture rather than
 *  typed in, because no event date is hard-coded anywhere in this project.
 */

const STEP_MS_HINT = 5; // seconds, documented in the copy — frames render server-side

export function ReplayPage({ eventId }: { eventId?: string }) {
  const { t } = useTranslation('pages');

  const [anchorId, setAnchorId] = useState<string | null>(null);
  const [anchorResolved, setAnchorResolved] = useState(false);
  const [plume, setPlume] = useState<PlumeFrames | null>(null);
  const [exposure, setExposure] = useState<ExposureRun | null>(null);
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
        if (live) setAnchorId(s.event_id);
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
  const runCaveats = (exposure as (ExposureRun & { caveats?: unknown[] }) | null)?.caveats ?? [];

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
                nothing forced. */}
            <div className="flex flex-col gap-2 glass-panel p-5 mt-4 group">
              <p className="m-0 text-base font-bold premium-gradient-text">{t('replay.forcingTitle')}</p>
              <p className="m-0 max-w-prose text-sm text-ink-2 leading-relaxed">{t('replay.forcingBody')}</p>
            </div>
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
