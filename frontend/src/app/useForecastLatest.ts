import { useEffect, useRef, useState } from 'react';
import { fetchCurrentsAgreement, fetchForecastLatest } from '../api/live';
import type { CurrentsAgreement, ForecastLatest } from '../api/live';

/** The two genuinely-live, cache-only reads Forecast mode needs.
 *
 *  Both are best-effort (`tryJson` resolves to `null` on any failure) — a
 *  demo that depends on either succeeding is a demo that can fail on stage.
 *  Separate from `useLiveExposure` because Forecast mode's own decision
 *  (tasks/phase7/03-nizar.md, 2026-08-09) is to show what these two endpoints
 *  actually have — rain, wind, GEFS exceedance, anomaly signal, currents
 *  disagreement — and say plainly that it does not yet produce a reef exposure
 *  score, rather than silently reuse the historical exposure path.
 */
export interface ForecastState {
  forecast: ForecastLatest | null;
  currents: CurrentsAgreement | null;
  loading: boolean;
}

export function useForecastLatest(active: boolean): ForecastState {
  const [state, setState] = useState<ForecastState>({
    forecast: null,
    currents: null,
    loading: true,
  });
  const seqRef = useRef(0);

  useEffect(() => {
    if (!active) return;
    const seq = ++seqRef.current;
    setState((s) => ({ ...s, loading: true }));
    void Promise.all([fetchForecastLatest(), fetchCurrentsAgreement()]).then(
      ([forecast, currents]) => {
        if (seq !== seqRef.current) return;
        setState({ forecast, currents, loading: false });
      },
    );
  }, [active]);

  return state;
}
