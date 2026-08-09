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

            <ul className="m-0 grid list-none gap-3 p-0" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(12rem, 1fr))' }}>
              {figures.figures.map((f) => (
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
                      <span className="flex aspect-4/3 w-full items-center justify-center rounded-sm bg-surface-2 text-2xs text-ink-3">
                        {t('provenance.noThumb')}
                      </span>
                    )}
                    <span dir="ltr" className="line-clamp-2 px-1 font-mono num text-2xs text-ink-3">
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
            className="fixed inset-4 z-60 flex flex-col gap-3 overflow-auto p-6 glass-card lg:inset-12"
            aria-describedby={undefined}
          >
            <Dialog.Title dir="ltr" className="m-0 font-mono num text-lg font-bold premium-gradient-text">
              {shown?.file}
            </Dialog.Title>
            {shown?.thumb ? (
              <img
                src={`${import.meta.env.BASE_URL}fixtures/${shown.thumb}`}
                alt={shown.caption}
                className="max-h-[55vh] w-auto self-start"
              />
            ) : null}
            <p dir="auto" className="m-0 max-w-prose text-xs text-ink-2">
              {shown?.caption}
            </p>
            <dl className="m-0 flex flex-wrap gap-x-6 gap-y-1 text-2xs text-ink-3">
              <div>
                <dt className="inline">{t('provenance.generated')} </dt>
                <dd className="m-0 inline font-mono num">
                  {shown?.generated ?? t('provenance.notStated')}
                </dd>
              </div>
              <div>
                <dt className="inline">{t('provenance.chain')} </dt>
                <dd className="m-0 inline">{shown?.source ?? t('provenance.notStated')}</dd>
              </div>
              <div>
                <dt className="inline">{t('provenance.fullRes')} </dt>
                <dd className="m-0 inline font-mono num" dir="ltr">
                  {shown?.full_path}
                </dd>
              </div>
            </dl>
            <Dialog.Close className="self-start mt-4 px-6 py-2 text-sm font-bold premium-button hover:premium-button-hover cursor-pointer">
              {t('provenance.close')}
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </PageShell>
  );
}
