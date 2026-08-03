import { create } from 'zustand';

export type ThemeChoice = 'light' | 'dark' | 'system';
export type Lang = 'en' | 'ar';
export type Mode = 'historical' | 'forecast' | 'scenario';

/** The layers a user can switch off. Mirrors the z-order in
 *  03-information-architecture.md §4; the basemap itself is not optional. */
export type LayerKey =
  | 'isobaths'
  | 'catchments'
  | 'rainfall'
  | 'plume'
  | 'reef'
  | 'outlets'
  | 'mooring'
  | 'modelGrid'
  | 'coverage'
  | 'labels';

/** Direction is derived from language, never stored separately — two sources of
 *  truth for direction is how a layout ends up half-mirrored. */
export const dirFor = (lang: Lang): 'ltr' | 'rtl' => (lang === 'ar' ? 'rtl' : 'ltr');

interface UiState {
  theme: ThemeChoice;
  lang: Lang;
  mode: Mode;
  /** Index into the active mode's timestep list. One cursor drives every
   *  time-varying layer, the hyetograph cursor and the risk cards together —
   *  01 §7 calls that choreography "the product". */
  cursor: number;
  layers: Record<LayerKey, boolean>;

  setTheme: (t: ThemeChoice) => void;
  setLang: (l: Lang) => void;
  setMode: (m: Mode, stepCounts: Record<Mode, number>) => void;
  setCursor: (i: number) => void;
  toggleLayer: (k: LayerKey) => void;
}

function fromUrl(): { lang: Lang; theme: ThemeChoice; mode: Mode } {
  const p = new URLSearchParams(window.location.search);
  const lang = p.get('lang') === 'ar' ? 'ar' : 'en';
  const t = p.get('theme');
  const theme: ThemeChoice = t === 'dark' || t === 'light' ? t : 'system';
  const m = p.get('mode');
  const mode: Mode =
    m === 'forecast' || m === 'scenario' || m === 'historical' ? m : 'historical';
  return { lang, theme, mode };
}

const initial = fromUrl();

export const useUi = create<UiState>((set) => ({
  theme: initial.theme,
  lang: initial.lang,
  mode: initial.mode,
  cursor: 0,
  layers: {
    isobaths: true,
    catchments: true,
    rainfall: true,
    plume: true,
    reef: true,
    outlets: true,
    mooring: true,
    // The honesty device is off by default — it is a thing you turn ON to make a
    // point about resolution, not permanent chrome.
    modelGrid: false,
    coverage: true,
    labels: true,
  },

  setTheme: (theme) => set({ theme }),
  setLang: (lang) => set({ lang }),

  /** 03 §2: "Mode switching preserves the time cursor where the ranges overlap
   *  and clamps otherwise, rather than resetting to zero. Resetting loses the
   *  user's place mid-demo." Clamping is the honest read of "overlap" when the
   *  modes have different step counts. */
  setMode: (mode, stepCounts) =>
    set((s) => ({ mode, cursor: Math.min(s.cursor, Math.max(0, (stepCounts[mode] ?? 1) - 1)) })),

  setCursor: (cursor) => set({ cursor: Math.max(0, cursor) }),
  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
}));
