import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchExposure,
  fetchReefZonePhotos,
  fetchReefZonesLive,
  uploadReefZonePhoto,
  type ExposureResult,
  type ExposureRun,
  type ProposedSensitivityWeight,
  type ReefZonePhoto,
  type ReefZoneRow,
} from '../api/live';
import { Link } from '../components/Link';
import { Empty, ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { FormulaChain, type Factor } from '../components/FormulaChain';
import { StatusBadge } from '../components/StatusBadge';
import { PlaceholderNote } from '../components/PlaceholderNote';
import { CaveatList } from '../components/CaveatList';
import { DiveSitesNearZone } from '../components/DiveSitesNearZone';
import { Card, CardGrid, PageShell, Section } from '../shell/PageShell';
import { IdText } from './AlertsPage';

/** One reef zone, at /reef-zones/:id.
 *
 *  There is no `GET /api/v1/reef-zones/{id}` — the detail is assembled from the
 *  list endpoint plus the `/photos` sub-resource.
 *
 *  Phase 7 additions:
 *  - WP2: Click-to-See-Why formula inspector (p4-12)
 *  - WP3: StatusBadge on weight cards, b7 adaptive sampling, b8 honesty
 */

interface PhotoState {
  photos: ReefZonePhoto[];
  proposed: ProposedSensitivityWeight;
}

/** Minimal geometric icons, currentColor, one stroke weight — they orient the
 *  four attribute cards without competing with the numbers. */
const svg = (path: ReactNode) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {path}
  </svg>
);
const ICON = {
  area: svg(<rect x="2.5" y="2.5" width="11" height="11" rx="1.5" />),
  depth: svg(<><path d="M2.5 5h11" /><path d="M2.5 9h11" /><path d="M6 12.5 8 14l2-1.5" /></>),
  park: svg(<path d="M8 2.5 13 4.5v4c0 3-2.2 4.7-5 5.5-2.8-.8-5-2.5-5-5.5v-4z" />),
  habitat: svg(<><path d="M8 14V6" /><path d="M8 8.5 5 6" /><path d="M8 8.5 11 6" /><path d="M8 6V2.5" /></>),
};

/** One attribute card: an icon + all-caps eyebrow, then the value large, then an
 *  optional note. Consistent so the four read as a set, not four one-offs. */
function AttrCard({
  icon,
  label,
  note,
  tooltip,
  children,
}: {
  icon: ReactNode;
  label: string;
  note?: string;
  /** A short explanation surfaced as a focusable info icon beside the label,
   *  instead of taking a line under the value. Keyboard- and SR-reachable. */
  tooltip?: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <div className="mb-1.5 flex items-center gap-1.5 text-ink-3">
        {icon}
        <span className="text-2xs font-semibold uppercase tracking-wide">{label}</span>
        {tooltip ? (
          <button
            type="button"
            title={tooltip}
            aria-label={tooltip}
            className="inline-flex cursor-help items-center rounded-full text-ink-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1"
            style={{ outlineColor: 'var(--accent)' }}
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 7.2v3.6" />
              <circle cx="8" cy="4.9" r="0.5" fill="currentColor" />
            </svg>
          </button>
        ) : null}
      </div>
      {children}
      {note ? <p className="m-0 mt-1.5 text-2xs text-ink-3">{note}</p> : null}
    </Card>
  );
}

/** Build the five Factor objects from formula_terms for FormulaChain */
function buildFactors(
  ft: Record<string, unknown>,
  t: (key: string) => string,
): Factor[] {
  const factors: Factor[] = [
    {
      key: 'plume_probability',
      label: t('formula.plumeProbability'),
      value: (ft.plume_probability as number) ?? 0,
      source: ft.plume_source as string | undefined,
    },
    {
      key: 'relative_sediment_intensity',
      label: t('formula.sedimentIntensity'),
      value: (ft.relative_sediment_intensity as number) ?? 0,
      source: ft.relative_sediment_intensity_source as string | undefined,
    },
    {
      key: 'exposure_duration_weight',
      label: t('formula.durationWeight'),
      value: (ft.exposure_duration_weight as number) ?? 0,
    },
    {
      key: 'habitat_sensitivity_weight',
      label: t('formula.sensitivityWeight'),
      value: (ft.habitat_sensitivity_weight as number) ?? 0,
      placeholder: ft.habitat_sensitivity_weight_status as string | undefined,
    },
    {
      key: 'confidence_adjustment',
      label: t('formula.confidenceAdj'),
      value: (ft.confidence_adjustment as number) ?? 0,
      source: ft.confidence_adjustment_reason as string | undefined,
      placeholder:
        typeof ft.confidence_adjustment_reason === 'string' &&
        (ft.confidence_adjustment_reason as string).startsWith('PLACEHOLDER')
          ? (ft.confidence_adjustment_reason as string)
          : undefined,
    },
  ];
  return factors;
}

function UploadResult({ photo }: { photo: ReefZonePhoto }) {
  const { t } = useTranslation('pages');
  const heuristic = photo.model_basis === 'heuristic_rule_v1';

  return (
    <div className="flex flex-col gap-2 rule bg-surface-2 p-3" data-upload-result="true">
      <p className="m-0 text-xs font-semibold">{t('reefZone.resultTitle')}</p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
        <dt className="text-ink-2">{t('reefZone.predictedClass')}</dt>
        <dd className="m-0">{t(`reefZone.class.${photo.predicted_class}`)}</dd>
        <dt className="text-ink-2">{t('reefZone.confidence')}</dt>
        <dd className="m-0">
          <ValueWithUnit value={photo.confidence} digits={2} provenance="modelled" />
        </dd>
        <dt className="text-ink-2">{t('reefZone.modelBasis')}</dt>
        <dd className="m-0">
          <IdText>{photo.model_basis}</IdText>
        </dd>
        <dt className="text-ink-2">{t('reefZone.modelVersion')}</dt>
        <dd className="m-0">
          {photo.model_version ? (
            <IdText>{photo.model_version}</IdText>
          ) : (
            <ValueWithUnit value={null} />
          )}
        </dd>
      </dl>
      <p className="m-0 max-w-prose text-2xs text-ink-2">
        {heuristic ? t('reefZone.heuristicWarning') : t('reefZone.trainedBasis')}
      </p>
    </div>
  );
}

/** The formula inspector panel — WP2 centrepiece */
function FormulaInspector({
  result,
  run,
}: {
  result: ExposureResult;
  run: ExposureRun;
}) {
  const { t } = useTranslation('tools');
  const ft = result.formula_terms;

  const factors = buildFactors(ft, t);
  const rawScore = (ft.raw_score as number) ?? 0;
  const scoreScale = (ft.score_scale as number) ?? 100;
  const riskScore = (ft.risk_score as number) ?? result.risk_score;

  const zoneFraction = ft.zone_fraction_affected as number | undefined;
  const nOverlayRows = ft.n_overlay_rows as number | undefined;
  const measureCrs = ft.measure_crs as string | undefined;
  const arrivalWindow = result.arrival_window_hours;
  const horizonHours = ft.horizon_hours as number | undefined;
  const contourTimesHit = ft.contour_times_hit as number[] | undefined;
  const modelVersions = run.model_versions ?? (ft.model_versions as Record<string, string> | undefined);
  const confidenceMembers = ft.confidence_members_exceeding as number | undefined;
  const confidenceTotal = ft.confidence_members_total as number | undefined;
  const confidenceThreshold = ft.confidence_threshold_value_mm as number | undefined;
  const caveats = (result as unknown as Record<string, unknown>).caveats as unknown[] | undefined;

  return (
    <div className="flex flex-col gap-5" data-formula-inspector="true">
      {/* The chain — the product identity */}
      <FormulaChain factors={factors} product={rawScore} scale={scoreScale} result={riskScore} />

      {/* Geometry */}
      <div className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h4 className="m-0 text-2xs font-semibold text-ink-2">{t('formula.geometryTitle')}</h4>
        <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
          <dt className="text-ink-2">{t('formula.zoneFraction')}</dt>
          <dd className="m-0">
            <ValueWithUnit value={zoneFraction ?? null} digits={6} provenance="modelled" />
          </dd>
          <dt className="text-ink-2">{t('formula.overlayRows')}</dt>
          <dd className="m-0">
            <ValueWithUnit value={nOverlayRows ?? null} digits={0} provenance="modelled" />
          </dd>
          <dt className="text-ink-2">{t('formula.measureCrs')}</dt>
          <dd className="m-0">{measureCrs ? <IdText>{measureCrs}</IdText> : '—'}</dd>
        </dl>
      </div>

      {/* Timing */}
      <div className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h4 className="m-0 text-2xs font-semibold text-ink-2">{t('formula.timingTitle')}</h4>
        <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
          <dt className="text-ink-2">{t('formula.arrivalWindow')}</dt>
          <dd className="m-0">
            {arrivalWindow
              ? `${arrivalWindow[0]}–${arrivalWindow[1]} h`
              : '—'}
          </dd>
          <dt className="text-ink-2">{t('formula.horizonHours')}</dt>
          <dd className="m-0">
            <ValueWithUnit value={horizonHours ?? null} digits={0} unit="h" provenance="modelled" />
          </dd>
          {contourTimesHit ? (
            <>
              <dt className="text-ink-2">{t('formula.contourTimesHit')}</dt>
              <dd className="m-0 font-mono num">{contourTimesHit.join(', ')} h</dd>
            </>
          ) : null}
        </dl>
      </div>

      {/* Model versions */}
      {modelVersions && Object.keys(modelVersions).length > 0 ? (
        <div className="flex flex-col gap-2 rule bg-surface-2 p-3">
          <h4 className="m-0 text-2xs font-semibold text-ink-2">{t('formula.versionsTitle')}</h4>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
            {Object.entries(modelVersions).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-ink-2">{k}</dt>
                <dd className="m-0"><IdText>{String(v)}</IdText></dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {/* Confidence detail */}
      {confidenceMembers !== undefined && confidenceTotal !== undefined ? (
        <div className="flex flex-col gap-2 rule bg-surface-2 p-3">
          <h4 className="m-0 text-2xs font-semibold text-ink-2">{t('formula.confidenceDetail')}</h4>
          <p className="m-0 text-2xs text-ink-2">
            {t('formula.confidenceMembers', {
              exceeding: confidenceMembers,
              total: confidenceTotal,
              threshold: confidenceThreshold?.toFixed(2) ?? '—',
            })}
          </p>
        </div>
      ) : null}

      {/* Caveats */}
      {caveats && caveats.length > 0 ? (
        <CaveatList items={caveats} title={t('formula.caveatsTitle')} />
      ) : null}
    </div>
  );
}

export function ReefZonePage({ zoneId }: { zoneId: string }) {
  const { t } = useTranslation('pages');
  const { t: tTools } = useTranslation('tools');

  const [zones, setZones] = useState<ReefZoneRow[] | null>(null);
  const [zonesFailed, setZonesFailed] = useState(false);
  const [photoState, setPhotoState] = useState<PhotoState | null>(null);
  const [photosFailed, setPhotosFailed] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [lastUpload, setLastUpload] = useState<ReefZonePhoto | null>(null);

  // WP2: exposure data for the formula inspector
  const [exposureRun, setExposureRun] = useState<ExposureRun | null>(null);
  const [exposureLoading, setExposureLoading] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const loadPhotos = useCallback(async () => {
    const p = await fetchReefZonePhotos(zoneId);
    if (p === null) {
      setPhotosFailed(true);
      return;
    }
    setPhotosFailed(false);
    setPhotoState({ photos: p.photos, proposed: p.proposed_sensitivity_weight });
  }, [zoneId]);

  useEffect(() => {
    let live = true;
    setZones(null);
    setPhotoState(null);
    setLastUpload(null);
    setUploadFailed(false);
    setExposureRun(null);
    setExposureLoading(true);
    setInspectorOpen(false);

    void fetchReefZonesLive().then((z) => {
      if (!live) return;
      if (z === null) setZonesFailed(true);
      else setZones(z);
    });
    void loadPhotos();

    // Load exposure for this zone — try all outlets to find the one that reaches this zone
    const OUTLETS = ['AQ-O01', 'AQ-O02', 'AQ-O03', 'AQ-O04', 'AQ-O05'];
    void Promise.all(
      OUTLETS.map((o) =>
        fetchExposure('AQ-2016-10-28', { outletId: o, horizonHours: 24 }),
      ),
    ).then((runs) => {
      if (!live) return;
      // Find a run that reached this zone
      for (const run of runs) {
        if (!run) continue;
        const match = run.results.find((r) => r.reef_zone_id === zoneId);
        if (match) {
          setExposureRun(run);
          setExposureLoading(false);
          return;
        }
      }
      setExposureLoading(false);
    });

    return () => {
      live = false;
    };
  }, [zoneId, loadPhotos]);

  const onFile = (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setUploadFailed(false);
    void uploadReefZonePhoto(zoneId, file).then(async (r) => {
      setUploading(false);
      if (r === null) {
        setUploadFailed(true);
        return;
      }
      setLastUpload(r);
      await loadPhotos();
    });
  };

  if (zonesFailed) {
    return (
      <PageShell title={t('reefZone.title')}>
        <ErrorState what={t('reefZone.errorTitle')} message={t('reefZone.errorBody')} />
      </PageShell>
    );
  }

  if (zones === null) {
    return (
      <PageShell title={t('reefZone.title')}>
        <Loading what={t('reefZone.loading')} />
      </PageShell>
    );
  }

  const zone = zones.find((z) => z.reef_zone_id === zoneId) ?? null;

  if (!zone) {
    return (
      <PageShell title={t('reefZone.title')}>
        <Empty title={t('reefZone.notFoundTitle')} body={t('reefZone.notFoundBody', { id: zoneId })} />
        <Link to="/reef-zones" className="text-xs underline">
          {t('reefZone.backToList')}
        </Link>
      </PageShell>
    );
  }

  const placeholder =
    zone.sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST';
  const proposed = photoState?.proposed ?? null;

  // Find the exposure result for this zone
  const exposureResult = exposureRun?.results.find((r) => r.reef_zone_id === zoneId) ?? null;

  return (
    <PageShell
      title={zone.zone_name ?? zone.reef_zone_id}
      lede={<IdText>{zone.reef_zone_id}</IdText>}
      actions={
        <Link to="/reef-zones" className="text-xs underline">
          {t('reefZone.backToList')}
        </Link>
      }
    >
      <Section label={t('reefZone.attributesLabel')}>
        <CardGrid>
          <AttrCard icon={ICON.area} label={t('reefZones.col.area')}>
            <ValueWithUnit
              value={zone.area_km2}
              digits={3}
              unit={t('units.km2')}
              provenance="measured"
              className="text-xl font-semibold"
            />
          </AttrCard>
          <AttrCard icon={ICON.depth} label={t('reefZones.col.depth')} tooltip={t('reefZones.depthNote')}>
            <ValueWithUnit
              value={zone.depth_median_m}
              digits={1}
              unit={t('units.m')}
              provenance="measured"
              className="text-xl font-semibold"
            />
          </AttrCard>
          <AttrCard icon={ICON.park} label={t('reefZones.col.park')}>
            <ValueWithUnit
              value={zone.marine_park_overlap_pct}
              digits={1}
              unit={t('units.pct')}
              provenance="measured"
              className="text-xl font-semibold"
            />
          </AttrCard>
          <AttrCard
            icon={ICON.habitat}
            label={t('reefZones.col.habitat')}
            note={zone.geomorphic_class ?? t('reefZone.noGeomorphic')}
          >
            <p className="m-0 text-md font-semibold text-ink">
              {zone.habitat_class ?? <ValueWithUnit value={null} />}
            </p>
          </AttrCard>
        </CardGrid>
      </Section>

      {/* p4-B — dive sites whose nearest zone is this one, with the inland caveat */}
      <Section label={t('reefZone.diveSites.label')}>
        <DiveSitesNearZone zoneId={zoneId} />
      </Section>

      {/* WP2 — Click-to-See-Why: formula inspector */}
      <Section label={tTools('formula.title')}>
        {exposureLoading ? (
          <Loading what="Loading exposure data…" />
        ) : exposureResult && exposureRun ? (
          <Card>
            <div className="flex items-baseline justify-between gap-2">
              <p className="m-0 text-2xs text-ink-2">
                {t('reefZone.riskScoreLabel', { defaultValue: 'Exposure risk score' })}
              </p>
              <button
                type="button"
                onClick={() => setInspectorOpen(!inspectorOpen)}
                aria-expanded={inspectorOpen}
                className="rule min-h-6 px-2 py-1 text-2xs text-accent underline"
              >
                {inspectorOpen ? 'Hide formula' : 'Show formula'}
              </button>
            </div>
            <ValueWithUnit
              value={exposureResult.risk_score}
              digits={2}
              provenance="modelled"
              className="text-lg font-semibold"
            />
            <p className="m-0 text-2xs text-ink-3">
              {exposureResult.risk_level} · from <IdText>{exposureRun.outlet_id}</IdText>
            </p>

            {inspectorOpen ? (
              <FormulaInspector result={exposureResult} run={exposureRun} />
            ) : null}
          </Card>
        ) : (
          <Card>
            <p className="m-0 text-2xs text-ink-2">
              No exposure run reached this zone within 24 hours from any outlet.
              This is a stated absence — the plume did not extend far enough.
            </p>
          </Card>
        )}
      </Section>

      {/* --- WP3: the separation. Two panels, never one table. --- */}
      <Section label={t('reefZone.weightsLabel')}>
        <p className="m-0 max-w-prose text-2xs text-ink-2">{t('reefZone.weightsIntro')}</p>
        <div className="grid gap-5 lg:grid-cols-2">
          {/* IN USE */}
          <Card>
            <StatusBadge variant="in_use" />
            <h3 className="m-0 text-sm font-bold">{t('reefZone.liveTitle')}</h3>
            <ValueWithUnit
              value={proposed?.live_sensitivity_weight ?? zone.sensitivity_weight}
              digits={2}
              provenance="modelled"
              className="text-lg"
            />
            <p className="m-0 text-2xs text-ink-2">
              {t('reefZone.liveStatus')}{' '}
              <IdText>
                {proposed?.live_sensitivity_weight_status ?? zone.sensitivity_weight_status}
              </IdText>
            </p>
            {placeholder ? (
              <PlaceholderNote flag="PLACEHOLDER_PENDING_MARINE_SCIENTIST" />
            ) : (
              <p className="m-0 max-w-prose text-2xs text-ink-2">
                {t('reefZone.liveReviewedNote')}
              </p>
            )}
          </Card>

          {/* NOT IN USE */}
          <Card className="border-dashed border-risk-high-stroke bg-surface-2">
            <StatusBadge variant="not_in_use" />
            <h3 className="m-0 text-sm font-bold">{t('reefZone.proposalTitle')}</h3>
            {photosFailed ? (
              <p className="m-0 text-2xs text-ink-2">{t('reefZone.photosUnavailable')}</p>
            ) : proposed === null ? (
              <Loading what={t('reefZone.loadingPhotos')} />
            ) : (
              <>
                <ValueWithUnit
                  value={proposed.proposed_value}
                  digits={2}
                  provenance="modelled"
                  className="text-lg"
                />
                {proposed.proposed_value === null ? (
                  <p className="m-0 text-2xs text-ink-2">
                    {t(`reefZone.proposalStatusValue.${proposed.status}`, {
                      defaultValue: proposed.status,
                    })}
                    {' — '}
                    {t('reefZone.proposalPhotos')}: {proposed.n_photos} of 3 required
                  </p>
                ) : (
                  <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
                    <dt className="text-ink-2">{t('reefZone.proposalStatus')}</dt>
                    <dd className="m-0">
                      {t(`reefZone.proposalStatusValue.${proposed.status}`, {
                        defaultValue: proposed.status,
                      })}
                    </dd>
                    <dt className="text-ink-2">{t('reefZone.proposalPhotos')}</dt>
                    <dd className="m-0">
                      <ValueWithUnit value={proposed.n_photos} digits={0} provenance="measured" />
                    </dd>
                  </dl>
                )}
                <p className="m-0 max-w-prose text-2xs text-ink-2">
                  {t('reefZone.proposalNote')}
                </p>
              </>
            )}
          </Card>
        </div>
      </Section>

      {/* b8 — Coral Health */}
      <Section label={t('reefZone.coralHealthLabel')}>
        <Card>
          <div className="flex flex-col gap-1">
            <label htmlFor="reef-photo" className="text-2xs font-semibold text-ink-2">
              {t('reefZone.uploadLabel')}
            </label>
            <input
              id="reef-photo"
              type="file"
              accept="image/*"
              disabled={uploading}
              onChange={(e) => {
                onFile(e.target.files?.[0] ?? null);
                e.target.value = '';
              }}
              className="text-xs text-ink"
            />
            <p className="m-0 max-w-prose text-2xs text-ink-3">{t('reefZone.uploadHint')}</p>
          </div>

          {uploading ? <Loading what={t('reefZone.uploading')} /> : null}
          {uploadFailed ? (
            <ErrorState what={t('reefZone.uploadFailedTitle')} message={t('reefZone.uploadFailedBody')} />
          ) : null}
          {lastUpload ? <UploadResult photo={lastUpload} /> : null}

          <p className="m-0 flex items-baseline gap-2 text-2xs text-ink-2">
            {t('reefZone.photosContributed')}
            {photoState ? (
              <ValueWithUnit value={photoState.photos.length} digits={0} provenance="measured" />
            ) : (
              <ValueWithUnit value={null} />
            )}
          </p>
        </Card>
      </Section>

      {/* b7 — Adaptive Sampling: infrastructure only, not demoable */}
      {exposureResult ? (
        <Section label={tTools('sampling.title')}>
          <Card>
            <StatusBadge
              variant={
                (exposureResult as unknown as Record<string, unknown>).adjusted_priority_status === 'FEEDBACK_APPLIED'
                  ? 'feedback_applied'
                  : 'no_feedback'
              }
            />
            <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-2xs">
              <dt className="text-ink-2">{tTools('sampling.adjustedPriority')}</dt>
              <dd className="m-0">
                <ValueWithUnit
                  value={(exposureResult as unknown as Record<string, unknown>).adjusted_priority as number | null ?? null}
                  digits={4}
                  provenance="modelled"
                />
              </dd>
            </dl>
            <p className="m-0 text-2xs text-ink-3">{tTools('sampling.dampenRule')}</p>
            <p className="m-0 rule bg-surface-2 p-2 text-2xs text-ink-2">
              {tTools('sampling.infrastructureNote')}
            </p>
          </Card>
        </Section>
      ) : null}

      {zone.caveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <CaveatList items={zone.caveats} />
        </Section>
      ) : null}
    </PageShell>
  );
}
