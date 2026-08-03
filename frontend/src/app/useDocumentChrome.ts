import { useEffect } from 'react';
import i18n from '../i18n';
import { dirFor, useUi, type Lang, type ThemeChoice } from './uiStore';

/** Puts lang, dir and data-theme on <html> — not on a wrapper div.
 *
 *  06 §1 is explicit about why: form controls, scrollbars and text selection
 *  read the *document* direction, and a wrapper leaves all three behind. The
 *  same applies to data-theme, which 02 §6 puts on :root so an explicit choice
 *  can beat the OS preference.
 *
 *  This hook is shared by `/` and by each /specimen pane, so the specimen
 *  exercises production code rather than a parallel path that can drift.
 */
export function useDocumentChrome() {
  const { theme, lang } = useUi();

  useEffect(() => {
    const root = document.documentElement;
    const dir = dirFor(lang);

    root.setAttribute('lang', lang);
    root.setAttribute('dir', dir);

    // 'system' means remove the attribute entirely and let the media query in
    // tokens.generated.css decide. Writing data-theme="system" would match
    // neither [data-theme="dark"] nor [data-theme="light"] and silently pin the
    // page to the :root light values.
    if (theme === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);

    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [theme, lang]);

  return { theme, lang, dir: dirFor(lang) };
}

/** Read chrome straight from the URL, for the specimen panes, which are real
 *  documents in iframes and must render their own combination on first paint
 *  rather than inheriting the parent's. */
export function chromeFromSearch(search: string): { theme: ThemeChoice; lang: Lang } {
  const p = new URLSearchParams(search);
  const t = p.get('theme');
  return {
    theme: t === 'dark' || t === 'light' ? t : 'system',
    lang: p.get('lang') === 'ar' ? 'ar' : 'en',
  };
}
