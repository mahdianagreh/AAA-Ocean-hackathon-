import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog } from 'radix-ui';
import { loadProvenance, loadSources, type Provenance, type Sources } from '../api/panels';

/** DoD item 5: the 34 figures plus the data-sources table.
 *
 *  This is the panel that makes the integrity claim concrete. Every layer traces to
 *  a named, licensed source, and every figure carries the caption the QA run wrote
 *  for it — not a caption written later to look good.
 *
 *  Two facts are shown rather than hidden, both from 07 §6:
 *   - the manifest lists 34 while 36 PNGs exist, so driving the panel off the
 *     manifest omits two. A decision, so it is stated with the count.
 *   - overview_01 is excluded entirely. Its own burned-in caption says the
 *     catchments in it are "a local test fixture… 5 latitude bands, not a
 *     watershed delineation." Best-looking figure in the set, and wrong.
 */
export function ProvenancePanel() {
  const { t } = useTranslation();
  const [p, setP] = useState<Provenance | null>(null);
  const [s, setS] = useState<Sources | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void Promise.all([loadProvenance(), loadSources()])
      .then(([pp, ss]) => {
        if (!live) return;
        setP(pp);
        setS(ss);
      })
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;
  if (!p || !s) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  const shown = p.figures.find((f) => f.file === open);

  return (
    <div className="flex flex-col gap-5" data-panel="provenance">
      <section className="flex flex-col gap-3">
        <h3 className="text-lg font-bold premium-gradient-text">{t('provenancePanel.figures')}</h3>
        <p className="text-xs text-ink-3 mt-1">
          {t('provenancePanel.counts', {
            shown: p.figures.length,
            manifest: p.manifest_count,
            disk: p.on_disk_count,
          })}
        </p>
        <p className="text-2xs text-ink-3">{t(p.excluded_reason_key)}</p>

        {/* Thumbnails only. Full-resolution is 19.7 MB across 33 files and the
            offline pack has to carry whatever ships, so the lightbox links to the
            file in the repo rather than bundling it. */}
        <ul className="grid grid-cols-2 gap-2 lg:grid-cols-3">
          {p.figures.map((f) => (
            <li key={f.file}>
              <button
                type="button"
                onClick={() => setOpen(f.file)}
                data-figure={f.file}
                className="flex w-full flex-col gap-2 glass-panel p-2 text-start transition-all hover:glass-panel-hover hover:scale-105 group/thumb cursor-pointer"
              >
                {/* A fixed 4:3 box with object-contain. The figures range from tall
                    portrait coastlines to wide cross-shore profiles, and letting each
                    set its own height made the grid ragged — one portrait figure
                    stretched its row to four times the others. Uniform tiles also mean
                    the eye compares captions rather than aspect ratios. */}
                {f.thumb ? (
                  <span className="flex aspect-4/3 w-full items-center justify-center overflow-hidden bg-black/5 rounded-md">
                    <img
                      src={`${import.meta.env.BASE_URL}fixtures/${f.thumb}`}
                      alt={f.caption.slice(0, 120)}
                      loading="lazy"
                      className="max-h-full max-w-full object-contain mix-blend-multiply group-hover/thumb:scale-110 transition-transform duration-500"
                    />
                  </span>
                ) : (
                  <span className="flex aspect-4/3 w-full items-center justify-center bg-black/5 rounded-md text-xs font-semibold text-ink-3">
                    {t('value.missing')}
                  </span>
                )}
                <span className="line-clamp-2 px-1 text-xs font-medium text-ink-2 group-hover/thumb:text-accent transition-colors">{f.file}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* The data-sources table. Attribution is a licence obligation for every one
          of these, and 13-economics.md §6 flags OSM's share-alike as the one that
          needs a decision before a paid contract. */}
      <section className="flex flex-col gap-3 mt-4">
        <h3 className="text-lg font-bold premium-gradient-text">{t('provenancePanel.sources')}</h3>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t('provenancePanel.sources')}>
          <table className="w-full border-collapse text-2xs">
            <tbody>
              {s.rows.map((r, i) => (
                <tr key={i} className="border-b border-hairline">
                  {r.map((c, j) => (
                    <td key={j} dir="auto" className="py-1 pe-3 align-top text-ink-2">
                      {c.replace(/\*\*/g, '').replace(/`/g, '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-2xs text-ink-3">{t(s.share_alike_note_key)}</p>
        <p className="text-2xs text-ink-3">
          {t('validation.source')} <code className="font-mono num">{s.source}</code>
        </p>
      </section>

      {/* The lightbox. Radix Dialog, so focus trap, Escape and the aria-modal
          semantics come from a primitive rather than being approximated. */}
      <Dialog.Root open={Boolean(open)} onOpenChange={(o) => !o && setOpen(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-60 bg-black/40 backdrop-blur-md data-[state=open]:animate-overlay-show" />
          <Dialog.Content
            className="fixed inset-4 z-60 flex flex-col gap-4 overflow-auto glass-card p-6 shadow-2xl lg:inset-12 data-[state=open]:animate-content-show"
            aria-describedby={undefined}
          >
            <Dialog.Title className="text-xl font-bold premium-gradient-text tracking-wide">{shown?.file}</Dialog.Title>
            {shown?.thumb ? (
              <img
                src={`${import.meta.env.BASE_URL}fixtures/${shown.thumb}`}
                alt={shown.caption}
                className="max-h-[55vh] w-auto self-start"
              />
            ) : null}
            <p dir="auto" className="max-w-prose text-xs text-ink-2">
              {shown?.caption}
            </p>
            <dl className="flex flex-wrap gap-x-6 gap-y-1 text-2xs text-ink-3">
              <div>
                <dt className="inline">{t('provenancePanel.generated')} </dt>
                <dd className="inline font-mono num">{shown?.generated ?? '—'}</dd>
              </div>
              <div>
                <dt className="inline">{t('provenancePanel.chain')} </dt>
                <dd className="inline">{shown?.source ?? '—'}</dd>
              </div>
              <div>
                <dt className="inline">{t('provenancePanel.fullRes')} </dt>
                <dd className="inline font-mono num">{shown?.full_path}</dd>
              </div>
            </dl>
            <Dialog.Close className="self-start premium-button px-6 py-2.5 text-sm font-bold mt-4 cursor-pointer hover:premium-button-hover">
              {t('common.close')}
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
