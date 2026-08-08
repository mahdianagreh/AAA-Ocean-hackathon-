import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { LimitationsPanel } from '../panels/LimitationsPanel';
import { loadValidation, type Validation } from '../api/panels';
import { fetchReefZonesLive, type ReefZoneRow } from '../api/live';
import { useUi } from '../app/uiStore';

/** The in-app limitations page, at /limitations.
 *
 *  The body of this page is the existing overlay panel, rendered inside the page
 *  frame rather than re-implemented. That panel derives its content from
 *  docs/pitch_limitations.md and docs/forcing_limitations.md, so the page cannot
 *  drift from the documents the team maintains — and a limitation fixed in the
 *  repo disappears here on the next derivation instead of lingering as a stale
 *  warning. Its "Arabic pending" marker behaviour comes along unchanged: bodies
 *  stay in their source language and say so, because a fluent machine
 *  translation of a scientific caveat is worse than an English one that is
 *  labelled English.
 *
 *  Two facts a reader of that document set would otherwise have to take on trust
 *  are added here from live data, not retyped:
 *
 *   - the reef zone caveats, straight off GET /api/v1/reef-zones — including the
 *     `sensitivity_weight_status` field, which literally reads
 *     PLACEHOLDER_PENDING_MARINE_SCIENTIST on every zone, and the 250 m uniform
 *     strip assumption that the real Allen Coral Atlas geometry replaced.
 *   - the plume engine's wind forcing, which is permanently
 *     ConstantWindField(0, 0) because no historical marine wind source exists in
 *     this repo. That string is read from the calibration record rather than
 *     quoted, so it cannot go stale silently either.
 */
export function LimitationsPage() {
  const { t } = useTranslation('tools');
  const lang = useUi((s) => s.lang);

  const [record, setRecord] = useState<Validation | null>(null);
  const [zones, setZones] = useState<ReefZoneRow[] | null>(null);
  const [zonesLoaded, setZonesLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    void loadValidation()
      .then((v) => live && setRecord(v))
      .catch(() => {
        /* the forcing section states its own absence */
      });
    void fetchReefZonesLive().then((rows) => {
      if (!live) return;
      setZones(rows);
      setZonesLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  const placeholderZones =
    zones?.filter((z) => z.sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST') ??
    [];

  // One caveat message per distinct text, across all zones — the same four
  // messages repeat on all eight and eight copies of each is noise, not honesty.
  const zoneCaveats = new Map<string, { message: string; source: string | null; field: string }>();
  for (const z of zones ?? []) {
    for (const raw of z.caveats) {
      const c = raw as { field?: string; message?: string; source?: string | null };
      if (!c.message) continue;
      if (!zoneCaveats.has(c.message)) {
        zoneCaveats.set(c.message, {
          message: c.message,
          source: c.source ?? null,
          field: c.field ?? '',
        });
      }
    }
  }

  const calibration = record?.calibration_fit ?? null;

  return (
    <PageShell title={t('limitations.title')} lede={t('limitations.lede')}>
      <Section label={t('limitations.documentsSection')}>
        <Card>
          {/* The panel already prints the Arabic-pending notice when the UI is in
              Arabic. This line says the same thing about the page as a whole, so
              a reader knows before scrolling rather than after. */}
          {lang === 'ar' ? (
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('limitations.arabicPending')}</p>
          ) : null}
          <LimitationsPanel />
        </Card>
      </Section>

      <Section label={t('limitations.liveSection')}>
        <Card>
          <h3 className="m-0 text-sm font-semibold">{t('limitations.forcingTitle')}</h3>
          <p className="m-0 max-w-prose text-xs text-ink-2">{t('limitations.forcingBody')}</p>
          {calibration?.forcing_is_placeholder ? (
            <>
              <p className="m-0 max-w-prose text-xs">
                <strong className="font-semibold">{t('limitations.forcingPermanent')}</strong>{' '}
                <span dir="ltr" className="text-ink-2">
                  {calibration.forcing_placeholder_reason}
                </span>
              </p>
              <p dir="ltr" className="m-0 max-w-prose text-2xs text-ink-2">
                {calibration.windage_caveat}
              </p>
              <p className="m-0 text-2xs text-ink-3">
                {t('limitations.source')}{' '}
                <code dir="ltr" className="font-mono num">
                  {calibration.source}
                </code>
              </p>
            </>
          ) : (
            <p className="m-0 text-xs text-ink-3">{t('limitations.forcingUnavailable')}</p>
          )}
        </Card>

        <Card>
          <h3 className="m-0 text-sm font-semibold">{t('limitations.reefTitle')}</h3>
          {!zonesLoaded ? (
            <p className="m-0 text-xs text-ink-3" aria-live="polite">
              {t('limitations.loading')}
            </p>
          ) : !zones?.length ? (
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('limitations.reefUnavailable')}</p>
          ) : (
            <>
              <p className="m-0 max-w-prose text-xs text-ink-2">
                {t('limitations.reefPlaceholder', {
                  n: placeholderZones.length,
                  total: zones.length,
                })}
              </p>
              <p className="m-0 text-2xs text-ink-3">
                {t('limitations.reefStatusField')}{' '}
                <code dir="ltr" className="font-mono num">
                  sensitivity_weight_status = PLACEHOLDER_PENDING_MARINE_SCIENTIST
                </code>
              </p>
              <ul className="m-0 flex list-none flex-col gap-3 p-0">
                {[...zoneCaveats.values()].map((c) => (
                  <li key={c.message} className="flex flex-col gap-1">
                    {c.field ? (
                      <code dir="ltr" className="font-mono num text-2xs text-ink-3">
                        {c.field}
                      </code>
                    ) : null}
                    {/* Verbatim from the API. Sourced prose, not UI chrome. */}
                    <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
                      {c.message}
                    </p>
                    {c.source ? (
                      <code dir="ltr" className="font-mono num text-2xs text-ink-3">
                        {c.source}
                      </code>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </Section>
    </PageShell>
  );
}
