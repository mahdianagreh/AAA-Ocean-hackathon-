import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchReefZonePhotos,
  fetchReefZonesLive,
  uploadReefZonePhoto,
  type ProposedSensitivityWeight,
  type ReefZonePhoto,
  type ReefZoneRow,
} from '../api/live';
import { Link } from '../components/Link';
import { Empty, ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { Card, CardGrid, PageShell, Section } from '../shell/PageShell';
import { Caveats, IdText } from './AlertsPage';

/** One reef zone, at /reef-zones/:id.
 *
 *  There is no `GET /api/v1/reef-zones/{id}` — the detail is assembled from the
 *  list endpoint plus the `/photos` sub-resource. That is recorded in live.ts
 *  and repeated here because "the detail endpoint must be missing, let me add a
 *  fetch for it" is the obvious wrong first move.
 *
 *  THE requirement on this page is the separation of two numbers that look
 *  identical and mean opposite things:
 *
 *    live_sensitivity_weight    — what the exposure engine multiplied by. Real,
 *                                 in use, and currently an unreviewed 1.0.
 *    proposed_sensitivity_weight — what the contributed photos would suggest.
 *                                 Pending marine-scientist review, in use
 *                                 nowhere, and NOT a correction anyone approved.
 *
 *  They are therefore in two separate panels, with different framing, each
 *  labelled with whether it is in use — never adjacent cells of one table, where
 *  the eye reads the pair as before/after. A proposal mistaken for the live
 *  weight would silently change every exposure number on the platform.
 */

interface PhotoState {
  photos: ReefZonePhoto[];
  proposed: ProposedSensitivityWeight;
}

/** The upload result renders `model_basis` verbatim and explains it in words.
 *  `heuristic_rule_v1` means no trained classifier exists on disk: the answer
 *  came from colour and texture rules and its confidence is capped at 0.55. A
 *  capped heuristic presented as a classifier is the exact claim this project
 *  has spent Phase 3 removing, so the caveat is part of the result, not a
 *  footnote under it. */
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

export function ReefZonePage({ zoneId }: { zoneId: string }) {
  const { t } = useTranslation('pages');

  const [zones, setZones] = useState<ReefZoneRow[] | null>(null);
  const [zonesFailed, setZonesFailed] = useState(false);
  const [photoState, setPhotoState] = useState<PhotoState | null>(null);
  const [photosFailed, setPhotosFailed] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [lastUpload, setLastUpload] = useState<ReefZonePhoto | null>(null);

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
    // Reset on a zone change, or the previous zone's photos flash under the new
    // zone's name for one paint — which on this page means the previous zone's
    // proposed weight beside this zone's live weight.
    setZones(null);
    setPhotoState(null);
    setLastUpload(null);
    setUploadFailed(false);

    void fetchReefZonesLive().then((z) => {
      if (!live) return;
      if (z === null) setZonesFailed(true);
      else setZones(z);
    });
    void loadPhotos();

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
      // The proposal is recomputed server-side from the photo count, so the
      // panel below is re-read rather than incremented locally.
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
          <Card>
            <p className="m-0 text-2xs text-ink-2">{t('reefZones.col.area')}</p>
            <ValueWithUnit
              value={zone.area_km2}
              digits={3}
              unit={t('units.km2')}
              provenance="measured"
              className="text-lg"
            />
          </Card>
          <Card>
            <p className="m-0 text-2xs text-ink-2">{t('reefZones.col.depth')}</p>
            <ValueWithUnit
              value={zone.depth_median_m}
              digits={1}
              unit={t('units.m')}
              provenance="measured"
              className="text-lg"
            />
            <p className="m-0 text-2xs text-ink-3">{t('reefZones.depthNote')}</p>
          </Card>
          <Card>
            <p className="m-0 text-2xs text-ink-2">{t('reefZones.col.park')}</p>
            <ValueWithUnit
              value={zone.marine_park_overlap_pct}
              digits={1}
              unit={t('units.pct')}
              provenance="measured"
              className="text-lg"
            />
          </Card>
          <Card>
            <p className="m-0 text-2xs text-ink-2">{t('reefZones.col.habitat')}</p>
            <p className="m-0 text-sm">{zone.habitat_class ?? <ValueWithUnit value={null} />}</p>
            <p className="m-0 text-2xs text-ink-3">
              {zone.geomorphic_class ?? t('reefZone.noGeomorphic')}
            </p>
          </Card>
        </CardGrid>
      </Section>

      {/* --- the separation. Two panels, never one table. --------------------- */}
      <Section label={t('reefZone.weightsLabel')}>
        <p className="m-0 max-w-prose text-2xs text-ink-2">{t('reefZone.weightsIntro')}</p>
        <div className="grid gap-5 lg:grid-cols-2">
          {/* IN USE. Plain surface, the same treatment as every other real value
              on the page. */}
          <Card>
            <span className="inline-block w-fit border border-hairline bg-surface-2 px-1.5 py-0.5 text-2xs font-semibold text-ink-2">
              {t('reefZone.chipInUse')}
            </span>
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
            <p className="m-0 max-w-prose text-2xs text-ink-2">
              {placeholder ? t('reefZone.livePlaceholderNote') : t('reefZone.liveReviewedNote')}
            </p>
          </Card>

          {/* NOT IN USE. Dashed, offset surface, and the chip says so in words —
              the border alone would be colour-and-form meaning with no text, and
              this is the one pair on the platform that must never be misread. */}
          <Card className="border-dashed border-risk-high-stroke bg-surface-2">
            <span className="inline-block w-fit border border-risk-high-stroke px-1.5 py-0.5 text-2xs font-semibold">
              {t('reefZone.chipNotInUse')}
            </span>
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
                <p className="m-0 max-w-prose text-2xs text-ink-2">
                  {t('reefZone.proposalNote')}
                </p>
              </>
            )}
          </Card>
        </div>
      </Section>

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
                // Cleared so the same file can be submitted twice — otherwise a
                // retry after a failure silently does nothing.
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

      {zone.caveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <Caveats items={zone.caveats} />
        </Section>
      ) : null}
    </PageShell>
  );
}
