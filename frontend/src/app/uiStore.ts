import { create } from 'zustand';

export type ThemeChoice = 'light' | 'dark' | 'system';
export type Lang = 'en' | 'ar';

/** Direction is derived from language, never stored separately — two sources of
 *  truth for direction is how a layout ends up half-mirrored. */
export const dirFor = (lang: Lang): 'ltr' | 'rtl' => (lang === 'ar' ? 'rtl' : 'ltr');

interface UiState {
  theme: ThemeChoice;
  lang: Lang;
  setTheme: (t: ThemeChoice) => void;
  setLang: (l: Lang) => void;
}

/** Language is a URL parameter, not only a stored preference — 06 §1. The demo
 *  has to be able to open straight into Arabic, and a bug report needs to be
 *  reproducible by pasting a link. */
function fromUrl(): { lang: Lang; theme: ThemeChoice } {
  const p = new URLSearchParams(window.location.search);
  const lang = p.get('lang') === 'ar' ? 'ar' : 'en';
  const t = p.get('theme');
  const theme: ThemeChoice = t === 'dark' || t === 'light' ? t : 'system';
  return { lang, theme };
}

const initial = fromUrl();

export const useUi = create<UiState>((set) => ({
  theme: initial.theme,
  lang: initial.lang,
  setTheme: (theme) => set({ theme }),
  setLang: (lang) => set({ lang }),
}));
