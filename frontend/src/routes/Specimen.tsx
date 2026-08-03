const COMBOS = [
  { theme: 'light', lang: 'en' },
  { theme: 'light', lang: 'ar' },
  { theme: 'dark', lang: 'en' },
  { theme: 'dark', lang: 'ar' },
] as const;

/** Four iframes, not four nested wrappers. The reason is specific.
 *
 *  Radix primitives portal to `document.body`. A Popover, Dialog, Select or
 *  Tooltip opened inside a `<div dir="rtl">` therefore renders in the
 *  *document's* direction — which means nested wrappers hide the single most
 *  important RTL bug, the one 00's risk register asks for per-primitive checks
 *  to catch.
 *
 *  06 §1 also locks `dir` and `lang` to `<html>` ("form controls, scrollbars and
 *  text selection read the document direction, and a wrapper leaves them
 *  behind"), and 02 §6 puts `data-theme` on `:root`. One document cannot hold
 *  two of either. Four real documents can.
 *
 *  Still one page, and still far cheaper than Storybook.
 */
export function Specimen() {
  return (
    <div className="flex min-h-screen flex-col gap-3 p-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold">Component specimen</h1>
        <p className="text-xs text-ink-2">
          Four real documents: light/dark × ltr/rtl. Each pane has its own{' '}
          <code className="font-mono">&lt;html lang dir data-theme&gt;</code>, so Radix portals,
          scrollbars and text selection are all checked in the direction they will ship in.
        </p>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-2">
        {COMBOS.map(({ theme, lang }) => (
          <figure key={`${theme}-${lang}`} className="m-0 flex min-h-96 flex-col rule">
            <figcaption className="flex items-center justify-between border-b border-hairline px-3 py-2 text-2xs">
              <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono">
                {theme} · {lang === 'ar' ? 'rtl' : 'ltr'}
              </span>
              <a
                className="text-accent underline"
                href={`/specimen?solo=1&theme=${theme}&lang=${lang}`}
                target="_blank"
                rel="noreferrer"
              >
                open
              </a>
            </figcaption>
            <iframe
              title={`specimen ${theme} ${lang}`}
              data-pane={`${theme}-${lang}`}
              src={`/specimen?solo=1&theme=${theme}&lang=${lang}`}
              className="min-h-96 flex-1 border-0"
            />
          </figure>
        ))}
      </div>
    </div>
  );
}
