import { useEffect, useState } from 'react';
import { fetchAlerts, fetchExposure, fetchPlumeFrames } from '../api/live';
import type { AlertRow, ExposureRun, PlumeFrames } from '../api/live';

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

export function useLiveExposure(eventId: string | undefined): LiveExposure {
  const [state, setState] = useState<LiveExposure>({
    exposure: null,
    plume: null,
    alerts: [],
    loading: true,
  });

  useEffect(() => {
    if (!eventId) return;
    let live = true;
    setState((s) => ({ ...s, loading: true }));

    void Promise.all([fetchExposure(eventId), fetchPlumeFrames(eventId), fetchAlerts()]).then(
      ([exposure, plume, alerts]) => {
        if (!live) return;
        setState({ exposure, plume, alerts, loading: false });
      },
    );

    return () => {
      live = false;
    };
  }, [eventId]);

  return state;
}
