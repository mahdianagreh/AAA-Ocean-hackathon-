import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import type { PlumeFrames } from '../api/live';
import { CaveatList } from './CaveatList';

/** The prediction as a picture — "where does the mud go", answered without
 *  generating anything.
 *
 *  Every pixel in the image has a provenance (a real Esri basemap, the plume the
 *  model actually predicted, real Allen Coral Atlas reef outlines), stated in a
 *  footer burned into the PNG itself and in the `…-Generated-Imagery: none`
 *  response header. (That header still carries the pre-rebrand product name as
 *  its vendor prefix, because it is emitted by the backend and renaming it is a
 *  backend change.) This panel adds one more place that provenance is stated:
 *  `plume.plume_source`, which flips from `'stub'` to `'particle-engine'` on its
 *  own the moment the real transport model is what actually ran — no change
 *  needed here when it does. A stub labelled as a stub is honest; a stub shown
 *  as a forecast is not, so the badge is not decorative. The engine is real as
 *  of Phase 7: `plume_source` now reads `'particle-engine'` for the anchor event.
 *
 *  The forcing note below renders `plume.provenance`/`plume.caveats` verbatim
 *  rather than asserting a fixed sentence about what the currents field is,
 *  because that is conditional on the checkout: it is real cached HYCOM data
 *  for the anchor event where `data/raw/currents/` happens to hold the archive,
 *  and the documented `PLACEHOLDER: ConstantCurrentField(0, 0)` otherwise. A
 *  hardcoded claim of "falls back to zero" would be simply wrong on a checkout
 *  where the archive is cached — this is not hypothetical, it is what Phase 7's
 *  own baseline check found on this repo. Wind has no such conditional: it is
 *  `ConstantWindField(0, 0)` unconditionally, because no historical marine wind
 *  source exists in this project at all.
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

      {/* 05-abd.md core-C: the three qualifications a judge must be able to read
          without asking — currents provenance (real HYCOM where cached, the
          documented placeholder otherwise), wind's permanent zero, and what that
          combination means for reading direction off these frames.
          `?? []` rather than a direct `.map`: an older cached response or a build
          skew between frontend and backend can still carry the pre-Phase-7 shape,
          and a missing field must degrade to "nothing to show" here, never to an
          uncaught render crash that takes out the whole side rail. */}
      <div className="flex flex-col gap-1 rule bg-surface-2 p-2">
        <p className="m-0 text-2xs font-semibold text-ink">{t('plumeMap.forcingTitle')}</p>
        {(plume.provenance ?? []).map((p, i) => (
          <p key={`${p.kind}-${i}`} className="m-0 text-2xs text-ink-2">
            {p.detail}
          </p>
        ))}
        <p className="m-0 text-2xs text-ink-2">{t('plumeMap.forcingWindStatement')}</p>
        {/* windage_fraction only ever appears alongside this caveat — the tie-break
            note travels WITH the parameter, never separately (design system §6.4). */}
        {plume.windage_is_tiebreak && plume.windage_caveat ? (
          <p className="m-0 text-2xs text-ink-2">{plume.windage_caveat}</p>
        ) : null}
        <p className="m-0 text-2xs text-ink-2">{t('plumeMap.forcingDiffusionBody')}</p>
      </div>

      <CaveatList items={plume.caveats ?? []} />
    </section>
  );
}
