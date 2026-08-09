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
  | 'divesites'
  | 'modelGrid'
  | 'coverage'
  | 'labels';

/** Direction is derived from language, never stored separately — two sources of
 *  truth for direction is how a layout ends up half-mirrored. */
export const dirFor = (lang: Lang): 'ltr' | 'rtl' => (lang === 'ar' ? 'rtl' : 'ltr');

/** Which overlay is open. 03 §1: the limitations text and the provenance panel are
 *  overlays rather than routes, because the whole product is one screen. */
export type Overlay = 'provenance' | 'limitations' | 'validation' | 'assistant' | 'journey' | null;

/** The six scenario controls. Defaults are the midpoints of what the documents
 *  actually say, not round numbers: transmission loss defaults to 50% because the
 *  measured range is 20–85%, and rainfall/sediment default to 100% because the
 *  unscaled event is the baseline the demo starts from. */
export interface Scenario {
  transmissionLoss: number;
  rainfallScale: number;
  antecedentWetness: number;
  windDirection: number;
  windSpeed: number;
  sedimentLoad: number;
}

export const SCENARIO_DEFAULTS: Scenario = {
  transmissionLoss: 50,
  rainfallScale: 100,
  antecedentWetness: 50,
  windDirection: 340,
  windSpeed: 5,
  sedimentLoad: 100,
};

interface UiState {
  theme: ThemeChoice;
  lang: Lang;
  mode: Mode;
  /** Index into the active mode's timestep list. One cursor drives every
   *  time-varying layer, the hyetograph cursor and the risk cards together —
   *  01 §7 calls that choreography "the product". */
  cursor: number;
  layers: Record<LayerKey, boolean>;
  overlay: Overlay;
  scenario: Scenario;

  setTheme: (t: ThemeChoice) => void;
  setLang: (l: Lang) => void;
  setMode: (m: Mode, stepCounts: Record<Mode, number>) => void;
  setCursor: (i: number) => void;
  toggleLayer: (k: LayerKey) => void;
  setOverlay: (o: Overlay) => void;
  setScenario: (k: keyof Scenario, v: number) => void;
  resetScenario: () => void;
}

/** Language and theme survive a reload; mode does not.
 *
 *  The Account page offers a language preference, and a preference that resets
 *  on navigation is not a preference. Mode is deliberately excluded — it is a
 *  property of what you are currently looking at, not of who you are.
 *
 *  Wrapped because localStorage throws outright in Safari private mode and
 *  under some embedded webviews, and a preference is never worth a blank page.
 *  The Playwright specs drive language through ?lang=, so the URL must still
 *  win over the stored value or every spec would inherit the previous run's
 *  choice — hence the read order in fromUrl(). */
const STORE_KEY = 'aq.prefs';

function readStored(): { lang?: Lang; theme?: ThemeChoice } {
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as { lang?: string; theme?: string };
    return {
      lang: parsed.lang === 'ar' || parsed.lang === 'en' ? parsed.lang : undefined,
      theme:
        parsed.theme === 'dark' || parsed.theme === 'light' || parsed.theme === 'system'
          ? parsed.theme
          : undefined,
    };
  } catch {
    return {};
  }
}

function persist(patch: { lang?: Lang; theme?: ThemeChoice }) {
  try {
    window.localStorage.setItem(STORE_KEY, JSON.stringify({ ...readStored(), ...patch }));
  } catch {
    // Storage unavailable or full. The in-memory choice still applies for this
    // session, which is the part the user can actually see.
  }
}

function fromUrl(): { lang: Lang; theme: ThemeChoice; mode: Mode } {
  const p = new URLSearchParams(window.location.search);
  const stored = readStored();

  // URL beats storage beats default, so a shared link always shows what it says.
  const urlLang = p.get('lang');
  const lang: Lang = urlLang === 'ar' ? 'ar' : urlLang === 'en' ? 'en' : (stored.lang ?? 'en');

  const t = p.get('theme');
  const theme: ThemeChoice =
    t === 'dark' || t === 'light' ? t : (stored.theme ?? 'system');

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
  overlay: null,
  scenario: { ...SCENARIO_DEFAULTS },
  layers: {
    isobaths: true,
    catchments: true,
    rainfall: true,
    plume: true,
    reef: true,
    outlets: true,
    mooring: true,
    // Dive sites are a reference layer, off by default: turned ON when the officer
    // is siting a survey. The honest coastal-vs-inland distinction lives on the
    // reef-zone page (with the distance caveat); here it is a plain POI overlay.
    divesites: false,
    // The honesty device is off by default — it is a thing you turn ON to make a
    // point about resolution, not permanent chrome.
    modelGrid: false,
    coverage: true,
    labels: true,
  },

  setTheme: (theme) => {
    persist({ theme });
    set({ theme });
  },
  setLang: (lang) => {
    persist({ lang });
    set({ lang });
  },

  /** 03 §2: "Mode switching preserves the time cursor where the ranges overlap
   *  and clamps otherwise, rather than resetting to zero. Resetting loses the
   *  user's place mid-demo." Clamping is the honest read of "overlap" when the
   *  modes have different step counts. */
  setMode: (mode, stepCounts) =>
    set((s) => ({ mode, cursor: Math.min(s.cursor, Math.max(0, (stepCounts[mode] ?? 1) - 1)) })),

  setCursor: (cursor) => set({ cursor: Math.max(0, cursor) }),
  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
  setOverlay: (overlay) => set({ overlay }),

  /** Moving a scenario control switches the mode to `scenario`.
   *
   *  03 §2 says scenario mode "inherits the base mode's range", so the cursor is
   *  untouched — only the mode changes. Leaving the mode alone while the numbers
   *  moved would mean the masthead said Historical while the view showed a what-if,
   *  which is the kind of quiet inconsistency a judge notices and a presenter
   *  cannot explain. */
  setScenario: (k, v) =>
    set((s) => ({ scenario: { ...s.scenario, [k]: v }, mode: 'scenario' })),

  resetScenario: () => set({ scenario: { ...SCENARIO_DEFAULTS } }),
}));
