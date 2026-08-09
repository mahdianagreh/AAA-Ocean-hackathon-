import { useEffect, useRef, useState } from 'react';
import { fetchAlerts, fetchExposure, fetchPlumeFrames } from '../api/live';
import type { AlertRow, ExposureRun, PlumeFrames } from '../api/live';
import { DATA_SOURCE } from '../api';
import type { Scenario } from './uiStore';
import { SCENARIO_DEFAULTS } from './uiStore';

/** The three genuinely-live calls, loaded independently of `useEventData`.
 *
 *  Deliberately a SEPARATE hook rather than folded into `useEventData`. That
 *  hook's `Promise.all` fails the whole load if any one call rejects — right for
 *  the five calls that already have a fixture fallback, wrong here: there is no
 *  fallback for "what did the model compute", so one slow or unreachable API must
 *  not block the map, the hyetograph and the risk cards from rendering with the
 *  data that IS available. `fetchExposure`/`fetchPlumeFrames`/`fetchAlerts` are
 *  already best-effort (null/[] on failure, never throw) — this hook just gives
 *  them a home that cannot regress the historical/offline path.
 *
 *  PHASE 7: now accepts scenario parameters. The two API-backed controls
 *  (rainfallMultiplier, transmissionLossOverride) are debounced ~400ms because
 *  a Radix slider fires on every pixel and the exposure calculation is not cheap.
 *  A request sequence number guards against out-of-order responses.
 */
export interface LiveExposure {
  exposure: ExposureRun | null;
  plume: PlumeFrames | null;
  alerts: AlertRow[];
  /** Distinguishes "still asking" from "asked, got nothing" — the caller renders
   *  a loading state for the first and a stated absence for the second, not the
   *  same blank for both. */
  loading: boolean;
}

export function useLiveExposure(
  eventId: string | undefined,
  scenario?: Scenario,
): LiveExposure {
  const [state, setState] = useState<LiveExposure>({
    exposure: null,
    plume: null,
    alerts: [],
    loading: true,
  });

  const seqRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Derive API parameters from the scenario.
  // Only transmissionLoss and rainfallScale have real API parameters;
  // the other four controls drive the client-side stand-in index only.
  const rainfallMultiplier = scenario
    ? scenario.rainfallScale / 100
    : undefined;
  const transmissionLossOverride = scenario
    ? scenario.transmissionLoss / 100
    : undefined;

  // Are the scenario params at their defaults (meaning "don't send them")?
  const isDefault =
    !scenario ||
    (scenario.rainfallScale === SCENARIO_DEFAULTS.rainfallScale &&
      scenario.transmissionLoss === SCENARIO_DEFAULTS.transmissionLoss);

  useEffect(() => {
    // Fixtures mode is the offline / deterministic demo path, and it must make
    // NO request off our own origin — offline-arabic's "no external requests"
    // gate (p4-H). These three calls have no fixture (there is no stored "what
    // the model computed"), so in fixtures mode they resolve to their honest
    // empty values without ever touching the network. Live exposure/plume/alerts
    // are a deliberate VITE_DATA_SOURCE=http choice, not the default.
    if (DATA_SOURCE !== 'http') {
      if (timerRef.current) clearTimeout(timerRef.current);
      setState({ exposure: null, plume: null, alerts: [], loading: false });
      return;
    }

    if (!eventId) return;

    // Cancel any pending debounce
    if (timerRef.current) clearTimeout(timerRef.current);

    const doFetch = () => {
      const seq = ++seqRef.current;
      setState((s) => ({ ...s, loading: true }));

      const params = isDefault
        ? {}
        : {
            rainfallMultiplier,
            transmissionLossOverride,
          };

      void Promise.all([
        fetchExposure(eventId, params),
        fetchPlumeFrames(eventId),
        fetchAlerts(),
      ]).then(([exposure, plume, alerts]) => {
        // Sequence guard: a slow early response must not overwrite a fast later one
        if (seq !== seqRef.current) return;
        setState({ exposure, plume, alerts, loading: false });
      });
    };

    // Debounce 400ms when scenario params change, instant on first load
    if (isDefault) {
      doFetch();
    } else {
      timerRef.current = setTimeout(doFetch, 400);
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, rainfallMultiplier, transmissionLossOverride, isDefault]);

  return state;
}
