import { useTranslation } from 'react-i18next';
import { Slider } from 'radix-ui';
import { useUi, type Scenario, SCENARIO_DEFAULTS } from '../app/uiStore';
import { ValueWithUnit } from './ValueWithUnit';

/** The six scenario controls — DoD item 2, "including transmission loss".
 *
 *  Phase 7 fix: this drawer now ACTUALLY sends `rainfall_multiplier` and
 *  `transmission_loss_override` to the API via `useLiveExposure` in the
 *  Dashboard. Before Phase 7, it only set zustand state with no effect.
 *
 *  Of the six controls, only TWO have real API parameters:
 *  - transmissionLoss → transmission_loss_override (0.20–0.85)
 *  - rainfallScale → rainfall_multiplier (0.5–2.0)
 *
 *  The other four (antecedentWetness, windDirection, windSpeed, sedimentLoad)
 *  drive the client-side stand-in index only, and are labelled as such.
 */

/** API-backed controls send their value to the real exposure calculation. */
const API_KEYS: Set<keyof Scenario> = new Set(['transmissionLoss', 'rainfallScale']);

const CONTROLS: Array<{
  key: keyof Scenario;
  min: number;
  max: number;
  step: number;
  unit: string;
  digits: number;
}> = [
  { key: 'transmissionLoss', min: 20, max: 85, step: 1, unit: '%', digits: 0 },
  { key: 'rainfallScale', min: 50, max: 200, step: 5, unit: '%', digits: 0 },
  { key: 'antecedentWetness', min: 0, max: 100, step: 5, unit: '%', digits: 0 },
  { key: 'windDirection', min: 0, max: 350, step: 10, unit: '°', digits: 0 },
  { key: 'windSpeed', min: 0, max: 20, step: 1, unit: 'm/s', digits: 0 },
  { key: 'sedimentLoad', min: 50, max: 200, step: 5, unit: '%', digits: 0 },
];

interface Preset {
  key: string;
  label: string;
  assumption: string;
  values: Partial<Scenario>;
}

const PRESETS: Preset[] = [
  {
    key: 'drySeason',
    label: 'Dry season',
    assumption: 'Little rain, most of it lost in the bed',
    values: { rainfallScale: 50, transmissionLoss: 85 },
  },
  {
    key: 'heavyRain',
    label: 'Heavy rain',
    assumption: 'Big storm, wet bed, more reaches the sea',
    values: { rainfallScale: 150, transmissionLoss: 40 },
  },
  {
    key: 'worstCase',
    label: 'Worst case',
    assumption: 'Maximum rain, minimum loss',
    values: { rainfallScale: 200, transmissionLoss: 20 },
  },
];

export function ScenarioDrawer() {
  const { t } = useTranslation();
  const { scenario, setScenario, resetScenario, mode } = useUi();

  const applyPreset = (preset: Preset) => {
    for (const [k, v] of Object.entries(preset.values)) {
      setScenario(k as keyof Scenario, v as number);
    }
  };

  return (
    <section className="flex flex-col gap-3" data-panel="scenario">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{t('scenario.title')}</h3>
        <button
          type="button"
          onClick={resetScenario}
          data-scenario-reset="true"
          className="rule min-h-6 px-2 py-1 text-2xs text-ink-2"
        >
          {t('scenario.reset')}
        </button>
      </div>

      {mode !== 'scenario' ? (
        <p className="text-2xs text-ink-3">{t('scenario.notActive')}</p>
      ) : null}

      {/* Presets: each states its assumption in one line */}
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => applyPreset(p)}
            className="rule min-h-6 border border-hairline bg-surface-2 px-2 py-1 text-2xs text-ink-2 hover:bg-surface"
            title={p.assumption}
          >
            {p.label}
          </button>
        ))}
      </div>

      <ul className="flex flex-col gap-3">
        {CONTROLS.map((c) => {
          const isApi = API_KEYS.has(c.key);
          return (
            <li key={c.key} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <label htmlFor={`sc-${c.key}`} className="text-ink-2">
                  {t(`scenario.${c.key}`)}
                  {!isApi ? (
                    <span className="ms-1 text-2xs text-ink-3">(index only)</span>
                  ) : null}
                </label>
                <ValueWithUnit
                  value={scenario[c.key]}
                  unit={c.unit}
                  digits={c.digits}
                  provenance="modelled"
                />
              </div>

              <Slider.Root
                id={`sc-${c.key}`}
                value={[scenario[c.key]]}
                min={c.min}
                max={c.max}
                step={c.step}
                onValueChange={([v]) => setScenario(c.key, v)}
                data-scenario={c.key}
                className="relative flex h-4 w-full touch-none items-center select-none"
              >
                <Slider.Track className="relative h-px w-full grow bg-hairline-2">
                  <Slider.Range className="absolute h-full bg-accent" />
                </Slider.Track>
                <Slider.Thumb
                  aria-label={t(`scenario.${c.key}`)}
                  className="block h-2.5 w-2.5 rotate-45 border border-ink bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                />
              </Slider.Root>

              <p className="text-2xs text-ink-3">{t(`scenario.${c.key}Note`)}</p>
            </li>
          );
        })}
      </ul>

      {/* 09 rule 8: never claim exactness. These controls change a transparent
          index, not a calibrated model, and saying so is the difference between a
          what-if and a pretence. */}
      <p className="rule bg-surface-2 p-2 text-2xs text-ink-2">{t('scenario.caveat')}</p>
    </section>
  );
}
