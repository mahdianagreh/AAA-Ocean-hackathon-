import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import type { PlumeFrames } from '../api/live';

/** The prediction as a picture — "where does the mud go", answered without
 *  generating anything.
 *
 *  Every pixel in the image has a provenance (a real Esri basemap, the plume the
 *  model actually predicted, real Allen Coral Atlas reef outlines), stated in a
 *  footer burned into the PNG itself and in `X-ReefShield-Generated-Imagery: none`
 *  on the response. This panel adds one more place that provenance is stated:
 *  `plume.plume_source`, which is `'stub'` today and flips to `'particle-engine'`
 *  by itself once the real transport model lands — no change needed here. A stub
 *  labelled as a stub is honest; a stub shown as a forecast is not, so the badge
 *  is not decorative.
 */
export function PlumeMapPanel({ plume }: { plume: PlumeFrames | null }) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  // The step whose image is actually decoded and on screen, vs. `step`, which is
  // "the one the last click asked for". They diverge for exactly as long as the
  // next frame takes to render server-side — measured at ~5 s on a machine also
  // running the data sweeps, not instant. Without this the old frame just sits
  // there through that gap and a click looks like it did nothing.
  const [shownStep, setShownStep] = useState(0);
  const requested = useRef(0);

  // Memoized rather than `plume?.frames ?? []` inline: that fallback allocates a
  // new empty array every render while `plume` is null, which is a fresh
  // dependency identity each time and would refire the preload effect below on
  // every parent re-render rather than only when `plume` actually changes.
  const frames = useMemo(() => plume?.frames ?? [], [plume]);

  useEffect(() => {
    if (!frames.length) return;
    const target = frames[Math.min(step, frames.length - 1)];
    requested.current = step;
    const img = new Image();
    img.onload = () => {
      // Only adopt it if this is still the most recently requested step — a slow
      // earlier frame resolving after a faster later one must not roll the view
      // backward.
      if (requested.current === step) setShownStep(step);
    };
    img.src = `${API_BASE}${target.url}`;
  }, [step, frames]);

  if (!plume || plume.frames.length === 0) {
    return (
      <section className="flex flex-col gap-1" data-panel="plume-map">
        <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
          {t('plumeMap.title')}
        </h2>
        <p className="text-2xs text-ink-3">{t('plumeMap.unavailable')}</p>
      </section>
    );
  }

  const shown = plume.frames[Math.min(shownStep, plume.frames.length - 1)];
  const pending = step !== shownStep;
  const isStub = plume.plume_source === 'stub';

  return (
    <section className="flex flex-col gap-2" data-panel="plume-map">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
          {t('plumeMap.title')}
        </h2>
        {/* Form over hue, same rule RiskCard's provisional marker follows — a
            coloured dot plus text, not coloured text alone. */}
        <span
          className="flex items-center gap-1 text-2xs text-ink-3"
          title={isStub ? t('plumeMap.stubNote') : t('plumeMap.realNote')}
        >
          {/* Square, not a dot — every status marker in this system is a form
              rather than a coloured circle (RiskCard's provisional marker,
              LayerToggle's indicator), so this stays consistent with that
              iconography rather than introducing a new shape. */}
          <span
            aria-hidden="true"
            className={`block h-2 w-2 shrink-0 border ${
              isStub
                ? 'border-risk-high-stroke bg-risk-high'
                : 'border-risk-minimal-stroke bg-risk-minimal'
            }`}
          />
          {isStub ? t('plumeMap.stub') : t('plumeMap.real')}
        </span>
      </div>

      {/* Plain <img>, no CDN: the backend bakes its own basemap, so this URL is
          the local API container either way — offline-safe by construction.
          Src only ever points at an already-loaded frame (preloaded above), so a
          slow render dims the CURRENT image rather than showing a blank one or
          silently doing nothing while the new one decodes. No spinner — 01 §7:
          nothing moves without being asked, and a fade is a direct response to
          the click, not motion invented on its own. */}
      <img
        src={`${API_BASE}${shown.url}`}
        alt={t('plumeMap.alt', { hours: shown.t_hours })}
        aria-busy={pending}
        className={`w-full border border-hairline transition-opacity ${
          pending ? 'opacity-50' : ''
        }`}
      />
      {pending ? (
        <p aria-live="polite" className="text-2xs text-ink-3">
          {t('plumeMap.rendering')}
        </p>
      ) : null}

      <div
        className="flex items-center gap-1 overflow-x-auto"
        role="group"
        aria-label={t('plumeMap.stepper')}
      >
        {plume.frames.map((f, i) => (
          <button
            key={f.t_hours}
            type="button"
            onClick={() => setStep(i)}
            aria-pressed={i === step}
            // Same selected-state language as ModeSwitch: border-accent +
            // bg-surface-2 + text-ink, not a filled button — one "this is chosen"
            // treatment across the interface rather than two.
            className={`min-h-6 shrink-0 border px-2 py-1 font-mono num text-2xs ${
              i === step
                ? 'border-accent bg-surface-2 text-ink'
                : 'border-hairline-2 text-ink-2'
            }`}
          >
            +{f.t_hours}h
          </button>
        ))}
      </div>

      <p className="text-2xs text-ink-3">{t('plumeMap.caveat')}</p>
    </section>
  );
}
