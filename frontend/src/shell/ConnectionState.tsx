import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, DATA_SOURCE } from '../api';
import type { Health } from '../api/types';

type State =
  | { kind: 'checking' }
  | { kind: 'live'; health: Health }
  | { kind: 'offline'; reason: string };

/** Connection state, and it has to be honest in both directions.
 *
 *  10-performance-and-offline.md: "connection state is visible, and degradation is
 *  explicit rather than silent." With the fixture client that means saying so —
 *  a green dot while serving committed GeoJSON would be a lie about where the
 *  numbers came from.
 *
 *  `model_available` is surfaced because it is false today: data/models/ does not
 *  exist, so the two model endpoints return 503. That is the project's real state
 *  and the masthead is the right place to admit it.
 */
export function ConnectionState() {
  const { t } = useTranslation();
  const [state, setState] = useState<State>({ kind: 'checking' });

  useEffect(() => {
    let live = true;
    void api()
      .health()
      .then((health) => live && setState({ kind: 'live', health }))
      .catch((e: Error) => live && setState({ kind: 'offline', reason: e.message }));
    return () => {
      live = false;
    };
  }, []);

  const label =
    state.kind === 'checking'
      ? t('connection.checking')
      : state.kind === 'offline'
        ? t('connection.offline')
        : DATA_SOURCE === 'fixtures'
          ? t('connection.snapshot')
          : t('connection.live');

  // Form, not only hue — a dot alone fails the same test the hazard ramp does.
  const mark = state.kind === 'live' ? (DATA_SOURCE === 'fixtures' ? '◐' : '●') : '○';

  const detail =
    state.kind === 'live'
      ? [
          `version ${state.health.version}`,
          `commit ${state.health.commit}`,
          state.health.model_available ? 'model registered' : t('connection.noModel'),
        ].join(' · ')
      : state.kind === 'offline'
        ? state.reason
        : '';

  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-2" title={detail}>
      <span aria-hidden="true" className="font-mono text-ink-3">
        {mark}
      </span>
      {label}
    </span>
  );
}
