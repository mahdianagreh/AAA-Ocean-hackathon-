import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { CaveatCard } from '../components/CaveatCard';
import { Field } from '../components/Field';
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
    <Field id={id} label={t(`sites.${key}`)}>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        dir="ltr"
        value={bbox[key]}
        onChange={(e) => setBbox((b) => ({ ...b, [key]: e.target.value }))}
        className="h-10 w-28 rounded-md border border-hairline bg-surface/50 px-3 font-mono num text-sm text-ink hover:border-accent focus:border-accent outline-none transition-colors"
      />
    </Field>
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
              <Field id={nameId} label={t('sites.nameLabel')}>
                <input
                  id={nameId}
                  type="text"
                  dir="auto"
                  value={siteName}
                  onChange={(e) => setSiteName(e.target.value)}
                  className="h-10 w-64 rounded-md border border-hairline bg-surface/50 px-3 text-sm text-ink hover:border-accent focus:border-accent outline-none transition-colors"
                />
              </Field>
              <button
                type="submit"
                disabled={state.kind === 'scoring'}
                className="h-11 rounded-md bg-ink px-6 text-sm font-bold text-ink-inverse transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
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

/** The overall score as a donut: filled arc = total / max, with the number
 *  through ValueWithUnit at the centre. role=img prunes the subtree, so the
 *  ariaLabel (built by the caller) carries the value for assistive tech. When no
 *  criterion scored (max 0) the centre is a gap, not a measured-looking 0.0. */
function ScoreDonut({ value, max, ariaLabel }: { value: number; max: number; ariaLabel: string }) {
  const r = 42;
  const circumference = 2 * Math.PI * r;
  const frac = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return (
    <div className="relative inline-flex h-28 w-28 shrink-0 items-center justify-center" role="img" aria-label={ariaLabel}>
      <svg width="112" height="112" viewBox="0 0 100 100" aria-hidden="true" className="-rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--hairline)" strokeWidth="9" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={`${circumference * frac} ${circumference}`}
        />
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center">
        {max > 0 ? (
          <>
            <ValueWithUnit value={value} digits={1} provenance="modelled" className="text-xl font-bold" />
            <span className="flex items-baseline gap-0.5 text-2xs text-ink-3">
              / <ValueWithUnit value={max} digits={0} />
            </span>
          </>
        ) : (
          <ValueWithUnit value={null} />
        )}
      </span>
    </div>
  );
}

function Result({ result }: { result: SiteScoreResponse }) {
  const { t } = useTranslation('tools');

  const byId = new Map(result.criteria.map((c) => [c.criterion, c]));
  const scored = result.criteria.filter((c) => c.status === 'scored' && c.score !== null);
  const total = scored.reduce((a, c) => a + (c.score ?? 0), 0);
  const maxPossible = scored.length * 2;
  // Null-safe narrow, matching the shared asCaveat pattern — a null or non-object
  // entry never reaches CaveatCard.
  const caveats = result.caveats.filter(
    (c): c is Caveat => !!c && typeof c === 'object' && typeof (c as Caveat).message === 'string',
  );
  const overallAria =
    maxPossible > 0
      ? `${t('sites.overallLabel')}: ${total.toFixed(1)} / ${maxPossible}`
      : t('sites.overallLabel');

  return (
    <>
      {/* Overall score — prominent donut + identity + the partial/complete note. */}
      <Card>
        <div className="flex flex-wrap items-center gap-6">
          <ScoreDonut value={total} max={maxPossible} ariaLabel={overallAria} />
          <div className="flex flex-col gap-1">
            <h3 className="m-0 flex flex-wrap items-baseline gap-2 text-sm font-semibold">
              <span dir="auto">{result.site_name ?? t('sites.unnamed')}</span>
              <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-2xs font-normal text-ink-3">
                {result.site_id}
              </code>
            </h3>
            <p className="m-0 text-xs text-ink-2">
              {t('sites.bboxIs')}{' '}
              <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
                {result.bbox.join(', ')}
              </code>
            </p>
            {/* Partial vs complete, stated. Only scored criteria count toward the
                total — summing a null as zero would understate a site for a
                criterion nobody can compute anywhere. */}
            <p className="m-0 text-xs text-ink-2">
              {t('sites.subtotal', { n: scored.length, total: result.criteria.length })}
            </p>
          </div>
        </div>
      </Card>

      {/* The scorecard. */}
      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('sites.criteriaTitle')}</h3>
        <ol className="m-0 flex list-none flex-col gap-4 p-0">
          {CRITERIA.map((id) => {
            const c = byId.get(id);
            if (!c) return null;
            const insufficient = c.status === 'insufficient_data' || c.score === null;
            const scoreVal = c.score ?? 0;
            return (
              <li key={id} data-criterion={id} className="flex flex-col gap-2 border-s-2 border-hairline-2 ps-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-col gap-0.5">
                    {/* Plain-language name is the headline; the raw C-key is small
                        secondary detail, not the label a reader has to decode. */}
                    <h4 className="m-0 text-xs font-bold text-ink">
                      <span dir="auto">{t(`sites.criterion.${id}`)}</span>
                    </h4>
                    <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-2xs text-ink-3">
                      {id}
                      {id === 'C6' ? ` · ${t('sites.constantNote')}` : ''}
                    </span>
                  </div>
                  {insufficient ? (
                    // Explicit "insufficient data" state — never a zero-filled bar.
                    <span className="inline-flex items-center rounded-full border border-hairline bg-surface px-2 py-0.5 text-2xs font-bold text-ink-2">
                      {t('sites.insufficient')}
                    </span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
                        <span
                          className="absolute inset-y-0 start-0 rounded-full"
                          style={{ width: `${(scoreVal / 2) * 100}%`, background: 'var(--accent)' }}
                        />
                      </span>
                      <span className="whitespace-nowrap text-xs">
                        <ValueWithUnit value={c.score} digits={1} provenance="modelled" />
                        <span className="text-ink-3"> / 2</span>
                      </span>
                    </div>
                  )}
                </div>

                {insufficient ? (
                  <p className="m-0 max-w-prose text-2xs text-ink-2">{t('sites.insufficientBody')}</p>
                ) : null}

                {c.evidence.length ? (
                  <ul className="m-0 flex list-none flex-col gap-2 p-0">
                    {c.evidence.map((e, i) => (
                      <li key={`${id}-${i}`} className="flex flex-col gap-1">
                        <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
                          {e.excerpt}
                        </p>
                        <span className="inline-flex w-fit items-center gap-1 rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-2xs text-ink-2">
                          <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
                            {e.source_file}
                          </code>
                          <span dir="auto" className="opacity-70">§ {e.section}</span>
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

      {/* Always rendered, never behind a disclosure — via the shared CaveatCard.
          The rubric's own one-site limit travels with every score. */}
      <Card>
        <h3 className="m-0 text-sm font-semibold">{t('sites.caveatsTitle')}</h3>
        <div className="flex flex-col gap-3">
          <CaveatCard severity="warning" message={t('sites.oneSite')} />
          {caveats.map((c, i) => (
            <CaveatCard
              key={`caveat-${i}`}
              severity={c.severity ?? 'note'}
              message={c.message ?? ''}
              source={c.source ?? null}
              field={c.field ?? null}
            />
          ))}
        </div>
      </Card>
    </>
  );
}
