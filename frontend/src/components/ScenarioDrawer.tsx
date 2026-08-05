import { useTranslation } from 'react-i18next';
import { Slider } from 'radix-ui';
import { useUi, type Scenario } from '../app/uiStore';
import { ValueWithUnit } from './ValueWithUnit';

/** The six scenario controls — DoD item 2, "including transmission loss".
 *
 *  Radix Slider here, unlike the time slider. The distinction is 06 §3's: these are
 *  ordinary magnitude controls whose fill direction SHOULD follow reading
 *  direction, so Radix's direction handling is exactly right. The time slider is
 *  the exception because it scrubs an axis that must not mirror.
 *
 *  Transmission loss is first, and it is the one that matters most. 20–85% of a
 *  Negev flood infiltrates the wadi bed and never reaches the sea, and the pipeline
 *  does not model it — so the honest move is to let a judge move it and watch the
 *  answer change, rather than bury a constant. That converts our largest
 *  unquantified uncertainty from a caveat in prose into something on screen.
 */
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

export function ScenarioDrawer() {
  const { t } = useTranslation();
  const { scenario, setScenario, resetScenario, mode } = useUi();

  return (
    <section className="flex flex-col gap-3" data-panel="scenario">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{t('scenario.title')}</h3>
        <button
          type="button"
          onClick={resetScenario}
          data-scenario-reset="true"
          // min-h-6: 24px, per 09's hit-area rule. py-0.5 gave 20px.
          className="rule min-h-6 px-2 py-1 text-2xs text-ink-2"
        >
          {t('scenario.reset')}
        </button>
      </div>

      {mode !== 'scenario' ? (
        <p className="text-2xs text-ink-3">{t('scenario.notActive')}</p>
      ) : null}

      <ul className="flex flex-col gap-3">
        {CONTROLS.map((c) => (
          <li key={c.key} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <label htmlFor={`sc-${c.key}`} className="text-ink-2">
                {t(`scenario.${c.key}`)}
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
              {/* Diamond, matching the time slider's handle — one handle language
                  across the interface rather than two. 09: the visible mark is
                  10px, so the touch target is extended by padding. */}
              {/* aria-label goes on the THUMB, not the Root. Radix puts
                  role="slider" on the thumb, so a label on the root leaves the
                  actual widget unnamed — axe caught all six of these as
                  aria-input-field-name violations. */}
              <Slider.Thumb
                aria-label={t(`scenario.${c.key}`)}
                className="block h-2.5 w-2.5 rotate-45 border border-ink bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
            </Slider.Root>

            <p className="text-2xs text-ink-3">{t(`scenario.${c.key}Note`)}</p>
          </li>
        ))}
      </ul>

      {/* 09 rule 8: never claim exactness. These controls change a transparent
          index, not a calibrated model, and saying so is the difference between a
          what-if and a pretence. */}
      <p className="rule bg-surface-2 p-2 text-2xs text-ink-2">{t('scenario.caveat')}</p>
    </section>
  );
}
