import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog } from 'radix-ui';
import { Card, PageShell, Section } from '../shell/PageShell';
import { loadProvenance, loadSources, type Provenance, type Sources } from '../api/panels';
import { fetchDataSources, type DataSourceRow } from '../api/live';

/** The QA figure gallery and the data-sources table, at /dashboard/provenance.
 *
 *  The overlay panel stays where it is and keeps working from the map screen.
 *  This page differs from it in one place that matters: THE DATA-SOURCES TABLE
 *  IS LIVE. The panel renders `public/fixtures/sources.json`, a flattened
 *  field/value transcription of the data dictionary; this page asks
 *  GET /api/v1/data-sources and renders what the API actually serves, column by
 *  column — product, version, resolution, access date, licence, limitations.
 *  If the ledger and the API ever disagree, that disagreement should be visible
 *  rather than papered over by reading the same file twice.
 *
 *  The figures still come from the derived provenance manifest, because they are
 *  files on disk in docs/qa_screenshots/ and no endpoint serves them. Both counts
 *  are shown — manifest and disk — for the same reason the panel shows them: the
 *  manifest lists fewer figures than exist, and driving the gallery off the
 *  manifest silently omits the difference. A stated count is a decision; a quiet
 *  one is an accident.
 */
export function ProvenancePage() {
  const { t } = useTranslation(['tools', 'common']);
  const [figures, setFigures] = useState<Provenance | null>(null);
  const [ledger, setLedger] = useState<Sources | null>(null);
  const [sources, setSources] = useState<DataSourceRow[] | null>(null);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [chainFilter, setChainFilter] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadProvenance()
      .then((p) => live && setFigures(p))
      .catch(() => {
        /* the gallery renders its own absent state */
      });
    void loadSources()
      .then((s) => live && setLedger(s))
      .catch(() => {
        /* the share-alike note is skipped rather than invented */
      });
    void fetchDataSources().then((rows) => {
      if (!live) return;
      setSources(rows);
      setSourcesLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  const shown = figures?.figures.find((f) => f.file === open) ?? null;

  // Filter by processing chain, derived from the figures' own `source` values —
  // never a fabricated category. The control appears only when there is more than
  // one chain to choose between.
  const chains = figures
    ? Array.from(new Set(figures.figures.map((f) => f.source).filter((s): s is string => Boolean(s)))).sort()
    : [];
  const visibleFigures = figures
    ? figures.figures.filter((f) => !chainFilter || f.source === chainFilter)
    : [];

  // Caption: a bold summary (first sentence) + supporting detail, instead of one
  // dense paragraph.
  const caption = shown?.caption ?? '';
  const capDot = caption.indexOf('. ');
  const capSummary = capDot > 0 ? caption.slice(0, capDot + 1) : caption;
  const capDetail = capDot > 0 ? caption.slice(capDot + 2) : '';

  return (
    <PageShell title={t('provenance.title')} lede={t('provenance.lede')}>
      <Section label={t('provenance.figuresSection')}>
        {!figures ? (
          <p className="m-0 text-xs text-ink-3" aria-live="polite">
            {t('provenance.loading')}
          </p>
        ) : (
          <Card>
            <p className="m-0 text-xs text-ink-2">
              {t('provenance.counts', {
                shown: figures.figures.length,
                manifest: figures.manifest_count,
                disk: figures.on_disk_count,
              })}
            </p>
            <p className="m-0 max-w-prose text-2xs text-ink-3">{t(figures.excluded_reason_key, { ns: 'common' })}</p>

            {chains.length > 1 ? (
              <div role="group" aria-label={t('provenance.filterLabel')} className="flex flex-wrap gap-2">
                <button
                  type="button"
                  aria-pressed={chainFilter === null}
                  onClick={() => setChainFilter(null)}
                  className={`rounded-full px-3 py-1 text-2xs font-semibold transition-colors cursor-pointer ${chainFilter === null ? 'bg-ink text-ink-inverse' : 'glass-panel text-ink-2 hover:border-accent'}`}
                >
                  {t('provenance.filterAll')}
                </button>
                {chains.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={chainFilter === c}
                    onClick={() => setChainFilter(c)}
                    className={`rounded-full px-3 py-1 text-2xs font-semibold transition-colors cursor-pointer ${chainFilter === c ? 'bg-ink text-ink-inverse' : 'glass-panel text-ink-2 hover:border-accent'}`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            ) : null}

            <ul className="m-0 grid list-none gap-3 p-0" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(12rem, 1fr))' }}>
              {visibleFigures.map((f) => (
                <li key={f.file}>
                  <button
                    type="button"
                    onClick={() => setOpen(f.file)}
                    data-figure={f.file}
                    className="flex w-full flex-col gap-2 p-2 text-start glass-panel glass-card-hover cursor-pointer"
                  >
                    {f.thumb ? (
                      <span className="flex aspect-4/3 w-full items-center justify-center overflow-hidden rounded-sm bg-surface-2">
                        <img
                          src={`${import.meta.env.BASE_URL}fixtures/${f.thumb}`}
                          alt={f.caption.slice(0, 120)}
                          loading="lazy"
                          className="max-h-full max-w-full object-contain"
                        />
                      </span>
                    ) : (
                      <span className="flex aspect-4/3 w-full items-center justify-center rounded-sm bg-surface-2 text-2xs text-ink-2">
                        {t('provenance.noThumb')}
                      </span>
                    )}
                    <span dir="ltr" className="line-clamp-2 px-1 font-mono num text-2xs text-ink-2">
                      {f.file}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </Section>

      <Section label={t('provenance.sourcesSection')}>
        {!sourcesLoaded ? (
          <p className="m-0 text-xs text-ink-3" aria-live="polite">
            {t('provenance.loading')}
          </p>
        ) : !sources?.length ? (
          // Not an error toast: the API being unreachable and the API having
          // nothing to say are the same "not available" state to a reader, and
          // both are better stated than blanked.
          <Card>
            <h3 className="m-0 text-sm font-semibold">{t('provenance.sourcesEmptyTitle')}</h3>
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('provenance.sourcesEmptyBody')}</p>
          </Card>
        ) : (
          <Card>
            <p className="m-0 text-xs text-ink-2">
              {t('provenance.sourcesCount', { n: sources.length })}
            </p>
            <div
              className="overflow-x-auto"
              tabIndex={0}
              role="region"
              aria-label={t('provenance.sourcesSection')}
            >
              <table className="w-full border-collapse text-xs mt-2">
                <caption className="sr-only">{t('provenance.sourcesSection')}</caption>
                <thead>
                  <tr className="border-b border-hairline-2 text-xs premium-gradient-text pb-2">
                    <th scope="col" className="py-2 pe-3 text-start font-bold">
                      {t('provenance.colProduct')}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start font-bold">
                      {t('provenance.colVersion')}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start font-bold">
                      {t('provenance.colResolution')}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start font-bold">
                      {t('provenance.colAccessDate')}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start font-bold">
                      {t('provenance.colLicence')}
                    </th>
                    <th scope="col" className="py-2 text-start font-bold">
                      {t('provenance.colLimitations')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((r) => (
                    <tr key={r.name} className="border-b border-hairline align-top hover:bg-surface/50 transition-colors group/row cursor-default">
                      <th scope="row" className="py-3 pe-3 text-start font-semibold text-ink group-hover/row:text-accent transition-colors">
                        <span dir="auto">{r.name}</span>
                        {r.substituted ? (
                          <span className="ms-2 rounded-sm border border-hairline-2 bg-surface-2 px-1 py-0.5 text-ink-2">
                            {t('provenance.substituted')}
                          </span>
                        ) : null}
                      </th>
                      <td dir="auto" className="py-2 pe-3 text-ink-2">
                        {r.product_version}
                      </td>
                      <td dir="auto" className="py-2 pe-3 text-ink-2">
                        {r.spatial_resolution ?? (
                          <span className="text-ink-3">{t('provenance.notStated')}</span>
                        )}
                      </td>
                      <td className="py-2 pe-3">
                        <code dir="ltr" className="font-mono num text-ink-2">
                          {r.access_date}
                        </code>
                      </td>
                      <td dir="auto" className="py-2 pe-3 text-ink-2">
                        {r.licence}
                      </td>
                      <td className="py-2 text-ink-2">
                        {r.limitations.length ? (
                          <ul className="m-0 flex list-disc flex-col gap-1 ps-4">
                            {r.limitations.map((l) => (
                              <li key={l} dir="auto" className="max-w-prose">
                                {l}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-ink-3">{t('provenance.noLimitations')}</span>
                        )}
                        {r.substitution_note ? (
                          <p dir="auto" className="m-0 mt-1 max-w-prose text-ink-3">
                            {r.substitution_note}
                          </p>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="m-0 text-2xs text-ink-3">{t('provenance.sourcesLive')}</p>
            {ledger ? (
              <>
                <p className="m-0 max-w-prose text-2xs text-ink-3">
                  {t(ledger.share_alike_note_key, { ns: 'common' })}
                </p>
                <p className="m-0 text-2xs text-ink-3">
                  {t('provenance.ledger')}{' '}
                  <code dir="ltr" className="font-mono num">
                    {ledger.source}
                  </code>
                </p>
              </>
            ) : null}
          </Card>
        )}
      </Section>

      {/* Radix Dialog for the lightbox, so focus trap, Escape and aria-modal come
          from a primitive rather than being approximated. */}
      <Dialog.Root open={Boolean(open)} onOpenChange={(o) => !o && setOpen(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-60 bg-canvas/80 backdrop-blur-sm" />
          <Dialog.Content
            className="fixed inset-4 z-60 flex flex-col gap-4 overflow-auto p-6 glass-card lg:inset-12"
            aria-describedby={undefined}
          >
            {/* File id as a small eyebrow; the bold summary is the real title. */}
            <div className="flex flex-col gap-1">
              <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-2xs text-ink-3">
                {shown?.file}
              </span>
              <Dialog.Title dir="auto" className="m-0 text-lg font-bold text-ink">
                {capSummary}
              </Dialog.Title>
            </div>

            {shown?.thumb ? (
              <img
                src={`${import.meta.env.BASE_URL}fixtures/${shown.thumb}`}
                alt={caption}
                className="max-h-[55vh] w-auto self-start rounded-md border border-hairline"
              />
            ) : null}

            {capDetail ? (
              <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
                {capDetail}
              </p>
            ) : null}

            {/* Metadata row, one small icon per item. */}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-2xs text-ink-2">
              <span className="inline-flex items-center gap-1.5">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2.5" y="3" width="11" height="10.5" rx="1" />
                  <path d="M2.5 6h11M5.5 3V1.5M10.5 3V1.5" />
                </svg>
                <span className="font-semibold">{t('provenance.generated')}</span>
                <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono">
                  {shown?.generated ?? t('provenance.notStated')}
                </span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M6.5 9.5a2.5 2.5 0 0 0 3.5 0l2-2a2.5 2.5 0 1 0-3.5-3.5l-.5.5" />
                  <path d="M9.5 6.5a2.5 2.5 0 0 0-3.5 0l-2 2a2.5 2.5 0 1 0 3.5 3.5l.5-.5" />
                </svg>
                <span className="font-semibold">{t('provenance.chain')}</span>
                <span dir="auto">{shown?.source ?? t('provenance.notStated')}</span>
              </span>
            </div>

            {/* "Open image" opens the served thumbnail in a new tab — labelled
                honestly, because that served asset is the downscaled JPG, not the
                full-resolution PNG. The true full-res image lives on disk at
                full_path (never web-served), shown beneath as the operator's
                reference rather than dressed up as a working link. */}
            {shown?.thumb ? (
              <a
                href={`${import.meta.env.BASE_URL}fixtures/${shown.thumb}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex w-fit items-center gap-1.5 text-xs font-semibold text-accent hover:underline"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M6 3H3v10h10v-3M9.5 2.5H13.5V6.5M13 3 7.5 8.5" />
                </svg>
                {t('provenance.openImage')}
              </a>
            ) : null}
            {shown?.full_path ? (
              <span className="text-2xs text-ink-3">
                {t('provenance.fullRes')}:{' '}
                <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
                  {shown.full_path}
                </code>
              </span>
            ) : null}

            <Dialog.Close className="self-start mt-2 rounded-md bg-ink px-6 py-2 text-sm font-bold text-ink-inverse transition-opacity hover:opacity-90 cursor-pointer">
              {t('provenance.close')}
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </PageShell>
  );
}
