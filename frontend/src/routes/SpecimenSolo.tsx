import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { chromeFromSearch, useDocumentChrome } from '../app/useDocumentChrome';
import { useUi } from '../app/uiStore';
import { SpecimenSections } from '../specimen/SpecimenSections';

/** One pane, chrome-free. Rendered inside an iframe by /specimen, and directly
 *  openable so a failing combination can be inspected on its own.
 *
 *  It applies theme and language through the SAME useDocumentChrome() hook that
 *  `/` uses. That matters: a specimen with its own theming path would drift from
 *  the app and stop proving anything.
 */
export function SpecimenSolo() {
  const { t } = useTranslation();
  const setTheme = useUi((s) => s.setTheme);
  const setLang = useUi((s) => s.setLang);

  // The store initialises from the URL, but this pane is a fresh document whose
  // search string carries the combination — push it in before first paint work.
  useEffect(() => {
    const { theme, lang } = chromeFromSearch(window.location.search);
    setTheme(theme);
    setLang(lang);
  }, [setTheme, setLang]);

  const { theme, dir } = useDocumentChrome();

  return (
    <main className="flex flex-col gap-6 p-4">
      <header className="flex items-baseline justify-between border-b border-hairline pb-2">
        <h1 className="text-md font-semibold">{t('specimen.title')}</h1>
        <span
          dir="ltr"
          style={{ unicodeBidi: 'isolate' }}
          className="font-mono text-2xs text-ink-3"
          data-chrome={`${theme}-${dir}`}
        >
          {theme} · {dir}
        </span>
      </header>
      <SpecimenSections />
    </main>
  );
}
