import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { loadEventSeries, timestepsFor, type EventSeries } from '../api/event';
import { riskFromPredictions, riskFromSeries } from '../api/risk';
import { loadPredictions, type Predictions } from '../api/predictions';
import type { Catchment, Outlet, ReefZone } from '../api/types';
import { useUi, type Mode } from './uiStore';

/** One load, one derivation, one cursor — read by the map, the chart and the cards.
 *
 *  This is the whole point of the vertical slice. If each region fetched its own
 *  copy the time-scrub choreography would drift: 01 §7 says a judge dragging the
 *  slider and watching rainfall, runoff, plume and exposure move in lockstep
 *  understands the system in three seconds, and lockstep needs a single source.
 */
export interface EventData {
  series: EventSeries;
  steps: string[];
  catchments: Catchment[];
  outlets: Outlet[];
  reef: ReefZone[];
  /** null when no artefact is registered, in which case the cards fall back to the
   *  transparent stand-in index and say so. */
  predictions: Predictions | null;
}

export function useEventData() {
  const [data, setData] = useState<EventData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const c = api();
    void Promise.all([
      loadEventSeries(),
      c.catchments(),
      c.outlets(),
      c.reefZones(),
      loadPredictions(),
    ])
      .then(([series, catchments, outlets, reef, predictions]) => {
        if (!live) return;
        setData({ series, steps: timestepsFor(series), catchments, outlets, reef, predictions });
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);

  return { data, error };
}

/** Steps available per mode.
 *
 *  Historical is the event window. Forecast and Scenario have no data behind them
 *  yet, so they inherit the same axis rather than pretending to a different one —
 *  and the UI says which mode is real. 03 §2 requires the cursor to survive a mode
 *  switch by clamping rather than resetting, which needs these counts.
 */
export function stepCounts(steps: string[]): Record<Mode, number> {
  return { historical: steps.length, forecast: steps.length, scenario: steps.length };
}

export function useRiskCards(data: EventData | null) {
  const cursor = useUi((s) => s.cursor);
  const scenario = useUi((s) => s.scenario);
  const mode = useUi((s) => s.mode);

  return useMemo(() => {
    if (!data) return [];

    // Real model output wherever it exists — it is strictly better evidence than
    // the proxy, and the proxy only ever existed because data/models/ was empty.
    //
    // Scenario mode is the one exception, and deliberately: the predictions are
    // model output at fixed inputs, so re-deriving them for an arbitrary
    // transmission-loss slider would mean inventing a prediction the model never
    // made. What-if therefore falls back to the transparent index, and the card
    // labels itself provisional again — which is the honest answer to "what would
    // happen if", given we cannot re-run a GBM in the browser.
    if (data.predictions && mode !== 'scenario') {
      return riskFromPredictions(data.predictions, data.catchments, cursor);
    }
    return riskFromSeries(data.series, data.catchments, cursor, scenario);
  }, [data, cursor, scenario, mode]);
}
