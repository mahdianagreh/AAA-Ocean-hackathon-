import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { scoreSite, type CriterionScore, type SiteScoreResponse } from '../api/live';

/** Site scoring, at /sites/score. An internal tool, and framed as one.
 *
 *  The six criteria are scored from real repo artefacts clipped to the box you
 *  give it — OSM drainage and buildings, the rainfall climatology, the reef zone
 *  geometry, the bathymetry raster. Two things it must never do:
 *
 *   1. RENDER A NULL SCORE AS ZERO. `score: null` with
 *      `status: "insufficient_data"` means no evidence source exists for that
 *      criterion at all — C6 is null for every location on earth, because
 *      "is this coast unmonitored?" is desk research, not a computable
 *      geospatial fact. Zero out of two says "we looked and it scored badly",
 *      which is a different and false claim. So a null renders as the missing
 *      state, never as a number.
 *   2. DROP THE ONE-SITE CAVEAT. The rubric was built and tuned against Aqaba
 *      alone; a score for any other coordinate is its first real test rather
 *      than a validated instrument. The API returns that caveat with every
 *      response, and it is shown with every response.
 *
 *  The bounding box is EPSG:4326 degrees in west, south, east, north order —
 *  which is what the API takes, so nothing is reordered on the way out.
 */

type State =
  | { kind: 'idle' }
  | { kind: 'scoring' }
  | { kind: 'scored'; result: SiteScoreResponse }
  | { kind: 'failed' };

interface Caveat {
  field?: string;
  message?: string;
  severity?: string;
  source?: string | null;
}

/** Aqaba's marine box, as the starting value — the one site the rubric has ever
 *  been run against, so the default is the honest default rather than a random
 *  square of sea. */
const DEFAULT_BBOX = { west: '34.95', south: '29.45', east: '35.00', north: '29.55' };

const CRITERIA: Array<CriterionScore['criterion']> = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6'];

export function SiteScorePage() {
  const { t } = useTranslation('tools');
  const westId = useId();
  const southId = useId();
  const eastId = useId();
  const northId = useId();
  const nameId = useId();

  const [bbox, setBbox] = useState(DEFAULT_BBOX);
  const [siteName, setSiteName] = useState('');
  const [state, setState] = useState<State>({ kind: 'idle' });
  const [invalid, setInvalid] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const nums = [bbox.west, bbox.south, bbox.east, bbox.north].map(Number);
    const ok =
      nums.every((n) => Number.isFinite(n)) && nums[0] < nums[2] && nums[1] < nums[3];
    setInvalid(!ok);
    if (!ok) return;

    setState({ kind: 'scoring' });
    void scoreSite([nums[0], nums[1], nums[2], nums[3]], siteName.trim() || undefined).then(
      (result) => setState(result ? { kind: 'scored', result } : { kind: 'failed' }),
    );
  };

  const field = (
    id: string,
    key: 'west' | 'south' | 'east' | 'north',
  ) => (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold">
        {t(`sites.${key}`)}
      </label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        dir="ltr"
        value={bbox[key]}
        onChange={(e) => setBbox((b) => ({ ...b, [key]: e.target.value }))}
        className="h-10 w-28 rounded-md border border-hairline bg-surface px-3 font-mono num text-sm text-ink"
      />
    </div>
  );

  return (
    <PageShell title={t('sites.title')} lede={t('sites.lede')}>
      <Section label={t('sites.inputSection')}>
        <Card>
          <p className="m-0 max-w-prose text-xs text-ink-2">{t('sites.internalTool')}</p>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <fieldset className="m-0 flex flex-wrap items-end gap-4 border-0 p-0">
              <legend className="text-xs font-semibold">{t('sites.bboxLegend')}</legend>
              {field(westId, 'west')}
              {field(southId, 'south')}
              {field(eastId, 'east')}
              {field(northId, 'north')}
            </fieldset>
            <p className="m-0 text-2xs text-ink-3">{t('sites.bboxHint')}</p>

            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor={nameId} className="text-xs font-semibold">
                  {t('sites.nameLabel')}
                </label>
                <input
                  id={nameId}
                  type="text"
                  dir="auto"
                  value={siteName}
                  onChange={(e) => setSiteName(e.target.value)}
                  className="h-10 w-64 rounded-md border border-hairline bg-surface px-3 text-sm text-ink"
                />
              </div>
              <button
                type="submit"
                disabled={state.kind === 'scoring'}
                className="h-10 rounded-md bg-ink px-4 text-xs font-bold text-ink-inverse disabled:opacity-50"
              >
                {state.kind === 'scoring' ? t('sites.scoring') : t('sites.score')}
              </button>
            </div>

            {invalid ? (
              <p role="alert" className="m-0 text-xs font-semibold text-ink">
                {t('sites.invalidBbox')}
              </p>
            ) : null}
          </form>
        </Card>
      </Section>

      <Section label={t('sites.resultSection')}>
        <div aria-live="polite" className="flex flex-col gap-5">
          {state.kind === 'idle' ? (
            <p className="m-0 text-xs text-ink-3">{t('sites.idle')}</p>
          ) : null}
          {state.kind === 'scoring' ? (
            <p className="m-0 text-xs text-ink-3">{t('sites.scoring')}</p>
          ) : null}
          {state.kind === 'failed' ? (
            <Card>
              <h3 className="m-0 text-sm font-semibold">{t('sites.failedTitle')}</h3>
              <p className="m-0 max-w-prose text-xs text-ink-2">{t('sites.failedBody')}</p>
            </Card>
          ) : null}

          {state.kind === 'scored' ? (
            <Result result={state.result} />
          ) : null}
        </div>
      </Section>
    </PageShell>
  );
}

function Result({ result }: { result: SiteScoreResponse }) {
  const { t } = useTranslation('tools');

  const byId = new Map(result.criteria.map((c) => [c.criterion, c]));
  const scored = result.criteria.filter((c) => c.status === 'scored' && c.score !== null);
  const total = scored.reduce((a, c) => a + (c.score ?? 0), 0);
  const caveats = (result.caveats as Caveat[]).filter((c) => c.message);

  return (
    <>
      <Card>
        <h3 className="m-0 flex flex-wrap items-baseline gap-2 text-sm font-semibold">
          <span dir="auto">{result.site_name ?? t('sites.unnamed')}</span>
          <code dir="ltr" className="font-mono num text-2xs font-normal text-ink-3">
            {result.site_id}
          </code>
        </h3>
        <p className="m-0 text-xs text-ink-2">
          {t('sites.bboxIs')}{' '}
          <code dir="ltr" className="font-mono num">
            {result.bbox.join(', ')}
          </code>
        </p>
        {/* The subtotal counts only the criteria that were actually scored, and
            says so — summing a null as zero would understate a site for a
            criterion nobody can compute anywhere. */}
        <p className="m-0 text-xs text-ink-2">
          {t('sites.subtotal', { n: scored.length, total: result.criteria.length })}{' '}
          <ValueWithUnit value={total} digits={1} provenance="modelled" />
          {' / '}
          <ValueWithUnit value={scored.length * 2} digits={0} />
        </p>
      </Card>

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('sites.criteriaTitle')}</h3>
        <ol className="m-0 flex list-none flex-col gap-4 p-0">
          {CRITERIA.map((id) => {
            const c = byId.get(id);
            if (!c) return null;
            const insufficient = c.status === 'insufficient_data' || c.score === null;
            return (
              <li key={id} data-criterion={id} className="flex flex-col gap-2">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h4 className="m-0 text-xs font-bold">
                    <span dir="ltr" className="font-mono num">
                      {id}
                    </span>{' '}
                    <span dir="auto">{t(`sites.criterion.${id}`)}</span>
                    {id === 'C6' ? (
                      <span className="ms-2 text-2xs font-normal text-ink-3">
                        (constant, no data required)
                      </span>
                    ) : null}
                  </h4>
                  {insufficient ? (
                    <span className="rounded-sm border border-hairline-2 bg-surface-2 px-2 py-0.5 text-2xs font-bold text-ink-2">
                      {t('sites.insufficient')}
                    </span>
                  ) : (
                    <span className="text-xs">
                      <ValueWithUnit value={c.score} digits={1} provenance="modelled" />
                      <span className="text-ink-3"> / 2</span>
                    </span>
                  )}
                </div>

                {insufficient ? (
                  <p className="m-0 max-w-prose text-2xs text-ink-2">
                    {t('sites.insufficientBody')}
                  </p>
                ) : null}

                {c.evidence.length ? (
                  <ul className="m-0 flex list-none flex-col gap-2 p-0">
                    {c.evidence.map((e, i) => (
                      <li
                        key={`${id}-${i}`}
                        className="flex flex-col gap-0.5 border-s-2 border-hairline-2 ps-3"
                      >
                        <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
                          {e.excerpt}
                        </p>
                        <span className="flex flex-wrap items-baseline gap-2 text-2xs text-ink-3">
                          <code dir="ltr" className="font-mono num">
                            {e.source_file}
                          </code>
                          <span dir="auto">§ {e.section}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="m-0 text-2xs text-ink-3">{t('sites.noEvidence')}</p>
                )}
              </li>
            );
          })}
        </ol>
      </Card>

      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('sites.narrativeTitle')}</h3>
        <p dir="auto" className="m-0 max-w-prose whitespace-pre-line text-xs text-ink-2">
          {result.narrative}
        </p>
      </Card>

      {/* Always rendered, never behind a disclosure. The rubric's own limit
          travels with every score it produces. */}
      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('sites.caveatsTitle')}</h3>
        <p className="m-0 max-w-prose text-xs font-semibold text-ink">{t('sites.oneSite')}</p>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {caveats.map((c, i) => (
            <li key={`caveat-${i}`} className="flex flex-col gap-0.5">
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
      </Card>
    </>
  );
}
