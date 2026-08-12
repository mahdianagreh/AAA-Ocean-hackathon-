import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { hrefWithSearch, navigate } from '../app/useRoute';
import { GAP_BAND, SWARM_FAILED_PREFIX, parseFinal } from '../app/recommendationText';
import {
  fetchRecommendation,
  triggerRecommendation,
  type AlertRow,
  type ResponseRecommendation,
} from '../api/live';
import { BAND_CLASS } from '../api/types';
import { DebateTable } from './DebateTable';

/** Phase 9 — the "Recommended Response" panel on an alert
 *  (tasks/phase9/00-phase9-plan.md §8.7). Lives inside AlertCard, one per alert.
 *
 *  GATE, ON THE FRONTEND TOO. The backend only runs the swarm automatically for
 *  `high`/`critical` risk_level (§2) — this panel renders nothing for anything
 *  below that, rather than showing a disabled button that would 409 if pressed.
 *  The human-override escape hatch (forcing a run below the gate) is a distinct
 *  operator power-tool this panel does not build; every trigger from here is the
 *  automatic path, so a `409` from the backend would mean the gate itself
 *  changed underneath this page, not that this panel got the check wrong.
 *
 *  POLLING, NOT A SUBSCRIPTION. Nizar's Supabase schema isn't the store behind
 *  this yet (backend/tasks/phase9/00-phase9-plan.md §3's persistence note: the
 *  swarm writes local SQLite, same reason exposure runs do) — so there is no
 *  realtime channel to subscribe to. A `setInterval` poll is the honest
 *  substitute, stopped the moment `completed_at` is set.
 *
 *  `completed_at`, never `status === 'finalized'`, is what stops polling: a
 *  swarm that crashes still gets `completed_at` stamped (main.py's
 *  `_run_swarm_background` exception handler), and a panel that only watches
 *  for `"finalized"` would poll forever after a real failure. */

const POLL_MS = 4000;

type Phase = 'idle' | 'starting' | 'polling' | 'error';

export function RecommendedResponsePanel({ alert }: { alert: AlertRow }) {
  const { t } = useTranslation('pages');
  const [rec, setRec] = useState<ResponseRecommendation | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  const eligible = alert.risk_level === 'high' || alert.risk_level === 'critical';
  if (!eligible) return null;

  function startPolling(id: string) {
    setPhase('polling');
    timerRef.current = setInterval(() => {
      void fetchRecommendation(id).then((r) => {
        if (!r) return;
        setRec(r);
        if (r.completed_at && timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      });
    }, POLL_MS);
  }

  async function onTrigger() {
    setPhase('starting');
    const r = await triggerRecommendation(alert.source_run_id);
    if (!r) {
      setPhase('error');
      return;
    }
    setRec(r);
    if (r.completed_at) {
      setPhase('polling'); // already done — render the finished view below
      return;
    }
    startPolling(r.id);
  }

  const failed = rec?.final_recommendation?.startsWith(SWARM_FAILED_PREFIX) ?? false;
  const parsed =
    rec?.completed_at && rec.final_recommendation && !failed ? parseFinal(rec.final_recommendation) : null;

  return (
    <section data-panel="recommended-response" className="flex flex-col gap-3 rule pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="m-0 text-xs font-bold uppercase tracking-wide text-ink-2">
          {t('recommendation.title')}
        </h4>
        {rec ? (
          <a
            href={hrefWithSearch(`/dashboard/recommendations/${rec.id}`)}
            onClick={(e) => {
              e.preventDefault();
              navigate(hrefWithSearch(`/dashboard/recommendations/${rec.id}`));
            }}
            className="text-2xs font-semibold text-accent hover:underline"
          >
            {t('recommendation.openFullPage')}
          </a>
        ) : null}
      </div>

      {phase === 'idle' ? (
        <>
          <p className="m-0 max-w-prose text-2xs text-ink-2">{t('recommendation.intro')}</p>
          <button
            type="button"
            onClick={() => void onTrigger()}
            className="w-fit h-9 rounded-full px-4 text-xs font-bold premium-button hover:premium-button-hover"
          >
            {t('recommendation.triggerButton')}
          </button>
        </>
      ) : null}

      {phase === 'starting' ? (
        <p className="m-0 text-2xs text-ink-3" aria-live="polite">
          {t('recommendation.starting')}
        </p>
      ) : null}

      {phase === 'error' ? (
        <p role="alert" className="m-0 text-2xs text-risk-critical">
          {t('recommendation.errorTrigger')}
        </p>
      ) : null}

      {rec ? <DebateTable rec={rec} /> : null}

      {rec?.completed_at && failed ? (
        <p role="alert" className="m-0 text-2xs text-risk-critical">
          {t('recommendation.errorSwarm', {
            message: rec.final_recommendation?.slice(SWARM_FAILED_PREFIX.length, -1).trim() ?? '',
          })}
        </p>
      ) : null}

      {rec?.completed_at && !failed && parsed ? (
        <div className="flex flex-col gap-3">
          <p className="m-0 max-w-prose text-sm leading-relaxed text-ink">{parsed.body}</p>

          {parsed.contested ? (
            <p className="m-0 max-w-prose rounded-card border-s-4 border-risk-moderate bg-surface-2 p-3 text-2xs text-ink-2">
              {t('recommendation.contestedNote', { reasoning: parsed.contested })}
            </p>
          ) : null}

          {rec.gaps.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <h5 className="m-0 text-2xs font-bold uppercase tracking-wide text-ink-2">
                {t('recommendation.gapsTitle')}
              </h5>
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {rec.gaps.map((g, i) => (
                  <li key={i} className="flex items-start gap-2 text-2xs text-ink-2">
                    {g.severity ? (
                      <span
                        className={`mt-0.5 inline-block shrink-0 border px-1 py-0.5 text-2xs ${BAND_CLASS[GAP_BAND[g.severity]]}`}
                      >
                        {t(`common:hazard.${GAP_BAND[g.severity]}`)}
                      </span>
                    ) : null}
                    <span className="max-w-prose">{g.gap_description}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="m-0 text-2xs text-ink-3">{t('recommendation.modelLabel', { model: rec.model })}</p>
        </div>
      ) : null}
    </section>
  );
}
