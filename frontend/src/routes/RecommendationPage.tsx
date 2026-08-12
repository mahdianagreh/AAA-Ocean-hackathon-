import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { Empty, ErrorState, Loading } from '../components/States';
import { hrefWithSearch, navigate } from '../app/useRoute';
import { AlertCard } from '../components/AlertCard';
import {
  fetchAlerts,
  fetchRecommendation,
  fetchReefZonesLive,
  type AlertRow,
  type ResponseRecommendation,
} from '../api/live';
import { BAND_CLASS } from '../api/types';
import { GAP_BAND, MAX_ROUNDS, SWARM_FAILED_PREFIX, parseFinal, roleLabel } from '../app/recommendationText';
import {
  downloadRecommendationPdf,
  type RecommendationPdfData,
  type RecommendationPdfLabels,
} from '../app/recommendationPdf';

/** Phase 9's "Recommended Response" swarm, as a full page rather than the
 *  collapsed inline panel on an alert card (`RecommendedResponsePanel.tsx`).
 *
 *  There is no list endpoint for recommendations (`recent_recommendations()`
 *  exists server-side but is not wired to a route), so the nav rail's
 *  "Response Swarm" tab and a bare `/dashboard/recommendations` URL both land
 *  here with no id — the `!recommendationId` branch below, not a real
 *  listing. A specific run is only reachable via the "open full page" link on
 *  that alert-card panel, which already holds the id. */

const POLL_MS = 4000;

function InAppLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <a
      href={hrefWithSearch(to)}
      onClick={(e) => {
        e.preventDefault();
        navigate(hrefWithSearch(to));
      }}
      className="w-fit text-xs font-semibold text-accent hover:underline"
    >
      {children}
    </a>
  );
}

export function RecommendationPage({ recommendationId }: { recommendationId?: string }) {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';
  const [rec, setRec] = useState<ResponseRecommendation | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [pdfBlocked, setPdfBlocked] = useState(false);
  const [eligibleAlerts, setEligibleAlerts] = useState<AlertRow[] | null>(null);
  const [zoneNames, setZoneNames] = useState<Record<string, string>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasLoadedRef = useRef(false);

  // Lets a swarm be started right from this page, without a detour through
  // Alerts first — only meaningful in the no-id/index view below, so this is
  // the only fetch skipped once a specific recommendation id is in the URL.
  useEffect(() => {
    if (recommendationId) return;
    let live = true;
    void fetchAlerts().then((rows) => {
      if (live) setEligibleAlerts(rows.filter((a) => a.risk_level === 'high' || a.risk_level === 'critical'));
    });
    void fetchReefZonesLive().then((zones) => {
      if (!live || !zones) return;
      const map: Record<string, string> = {};
      for (const zone of zones) if (zone.zone_name) map[zone.reef_zone_id] = zone.zone_name;
      setZoneNames(map);
    });
    return () => {
      live = false;
    };
  }, [recommendationId]);

  useEffect(() => {
    if (!recommendationId) return;
    const id = recommendationId;
    let cancelled = false;
    hasLoadedRef.current = false;
    setRec(null);
    setLoadFailed(false);

    function poll() {
      void fetchRecommendation(id).then((r) => {
        if (cancelled) return;
        if (r) {
          hasLoadedRef.current = true;
          setRec(r);
          if (r.completed_at && timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
        } else if (!hasLoadedRef.current) {
          setLoadFailed(true);
        }
      });
    }

    poll();
    timerRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [recommendationId]);

  if (!recommendationId) {
    return (
      <PageShell title={t('recommendationPage.title')} lede={t('recommendationPage.indexLede')}>
        {eligibleAlerts === null ? (
          <Loading what={t('recommendationPage.loadingAlerts')} />
        ) : eligibleAlerts.length > 0 ? (
          <Section label={t('recommendationPage.startSection')}>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {eligibleAlerts.map((a) => (
                <li key={a.alert_id}>
                  <AlertCard alert={a} zoneName={zoneNames[a.reef_zone_id]} />
                </li>
              ))}
            </ul>
          </Section>
        ) : (
          <Empty title={t('recommendationPage.noIdTitle')} body={t('recommendationPage.noIdBody')} />
        )}
        <InAppLink to="/alerts">{t('recommendationPage.backToAlerts')}</InAppLink>
      </PageShell>
    );
  }

  if (loadFailed) {
    return (
      <PageShell title={t('recommendationPage.title')}>
        <ErrorState what={t('recommendationPage.notFoundTitle')} message={t('recommendationPage.notFoundBody')} />
        <InAppLink to="/alerts">{t('recommendationPage.backToAlerts')}</InAppLink>
      </PageShell>
    );
  }

  if (!rec) {
    return (
      <PageShell title={t('recommendationPage.title')}>
        <Loading what={t('recommendationPage.loading')} />
      </PageShell>
    );
  }

  const currentRound = Math.max(0, ...rec.turns.map((turn) => turn.round));
  const running = !rec.completed_at;
  const failed = rec.final_recommendation?.startsWith(SWARM_FAILED_PREFIX) ?? false;
  const parsed =
    rec.completed_at && rec.final_recommendation && !failed ? parseFinal(rec.final_recommendation) : null;
  const failedMessage = failed
    ? t('recommendation.errorSwarm', {
        message: rec.final_recommendation?.slice(SWARM_FAILED_PREFIX.length, -1).trim() ?? '',
      })
    : null;

  const rounds = Array.from(new Set(rec.turns.map((turn) => turn.round))).map((round) => ({
    round,
    turns: rec.turns.filter((turn) => turn.round === round),
  }));

  const evidenceAll = Array.from(
    new Set([...rec.turns.flatMap((turn) => turn.evidence_cited), ...rec.verdicts.flatMap((v) => v.evidence_cited)]),
  );

  const briefEntries = Object.entries(rec.severity_brief ?? {}).map(([key, value]) => ({
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value),
  }));

  const triggeredByText =
    rec.triggered_by === 'human_override'
      ? t('recommendationPage.triggeredOverride')
      : t('recommendationPage.triggeredAuto');

  function onDownload() {
    const data: RecommendationPdfData = {
      eventId: rec!.event_id,
      runId: rec!.run_id,
      statusLabel: t(`recommendationPage.statusValue.${rec!.status}`),
      model: rec!.model,
      triggeredByText,
      createdAt: rec!.created_at,
      completedAt: rec!.completed_at,
      briefEntries,
      rounds: rounds.map((r) => ({
        round: r.round,
        turns: r.turns.map((turn) => ({
          roleLabel: roleLabel(t, turn.agent_role),
          content: turn.content,
          evidence: turn.evidence_cited,
        })),
      })),
      verdicts: rec!.verdicts.map((v) => ({
        verdictLabel: t(`recommendation.verdict.${v.verdict}`),
        reasoning: v.reasoning,
        evidence: v.evidence_cited,
      })),
      finalBody: parsed?.body ?? null,
      contestedNote: parsed?.contested ? t('recommendation.contestedNote', { reasoning: parsed.contested }) : null,
      failedMessage,
      convergedText: rec!.converged
        ? t('recommendation.convergedYes', { rounds: rec!.rounds_used, max: MAX_ROUNDS })
        : t('recommendation.convergedNo', { max: MAX_ROUNDS }),
      gaps: rec!.gaps.map((g) => ({
        severityLabel: g.severity ? t(`common:hazard.${GAP_BAND[g.severity]}`) : null,
        description: g.gap_description,
      })),
      evidenceAll,
    };

    const labels: RecommendationPdfLabels = {
      brand: 'AQABA AQUA AI',
      docTitle: t('recommendationPage.pdfTitle'),
      metaEvent: t('recommendationPage.metaEvent'),
      metaRun: t('recommendationPage.metaRun'),
      metaStatus: t('recommendationPage.metaStatus'),
      metaModel: t('recommendationPage.metaModel'),
      metaTriggeredBy: t('recommendationPage.metaTriggeredBy'),
      metaCreated: t('recommendationPage.metaCreated'),
      metaCompleted: t('recommendationPage.metaCompleted'),
      notCompleted: t('recommendationPage.notCompleted'),
      briefSection: t('recommendationPage.briefSection'),
      briefEmpty: t('recommendationPage.briefEmpty'),
      transcriptSection: t('recommendationPage.transcriptSection'),
      transcriptEmpty: t('recommendationPage.transcriptEmpty'),
      transcriptRound: t('recommendationPage.roundLabel'),
      evidenceLabel: t('recommendationPage.evidenceLabel'),
      evidenceNone: t('recommendation.evidenceNone'),
      verdictsSection: t('recommendationPage.verdictsSection'),
      verdictsEmpty: t('recommendationPage.verdictsEmpty'),
      resultSection: t('recommendationPage.resultSection'),
      resultNone: t('recommendationPage.resultNone'),
      limitationsSection: t('recommendationPage.limitationsSection'),
      limitationsEmpty: t('recommendationPage.limitationsEmpty'),
      evidenceSection: t('recommendationPage.evidenceSection'),
      evidenceEmpty: t('recommendationPage.evidenceEmpty'),
      footer: t('recommendationPage.pdfFooter'),
    };

    setPdfBlocked(!downloadRecommendationPdf(data, { lang, labels }));
  }

  return (
    <PageShell
      title={t('recommendationPage.title')}
      lede={
        <span className="flex flex-col gap-0.5">
          <span>{t('recommendationPage.lede')}</span>
          <span dir="ltr" className="font-mono num text-2xs text-ink-3" style={{ unicodeBidi: 'isolate' }}>
            {rec.event_id ?? '—'} · {rec.run_id}
          </span>
          {running ? (
            <span className="text-2xs text-ink-3" aria-live="polite">
              {currentRound > 0
                ? t('recommendation.runningRound', { round: currentRound, max: MAX_ROUNDS })
                : t('recommendation.running')}
            </span>
          ) : null}
        </span>
      }
      actions={
        <div className="flex flex-col items-end gap-1.5">
          <button
            type="button"
            onClick={onDownload}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border-2 border-accent px-4 text-xs font-bold text-accent transition-colors hover:bg-accent/10"
          >
            {t('recommendationPage.download')}
          </button>
          {pdfBlocked ? (
            <span role="alert" className="max-w-[14rem] text-end text-2xs text-risk-critical">
              {t('recommendationPage.pdfBlocked')}
            </span>
          ) : null}
        </div>
      }
    >
      <Card>
        <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-1.5 text-2xs text-ink-2 sm:grid-cols-3">
          <div>
            <dt className="font-semibold text-ink-3">{t('recommendationPage.metaStatus')}</dt>
            <dd className="m-0">{t(`recommendationPage.statusValue.${rec.status}`)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-3">{t('recommendationPage.metaModel')}</dt>
            <dd dir="ltr" className="m-0 font-mono" style={{ unicodeBidi: 'isolate' }}>
              {rec.model}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-3">{t('recommendationPage.metaTriggeredBy')}</dt>
            <dd className="m-0">{triggeredByText}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-3">{t('recommendationPage.metaCreated')}</dt>
            <dd dir="ltr" className="m-0 font-mono num" style={{ unicodeBidi: 'isolate' }}>
              {rec.created_at}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-3">{t('recommendationPage.metaCompleted')}</dt>
            <dd dir="ltr" className="m-0 font-mono num" style={{ unicodeBidi: 'isolate' }}>
              {rec.completed_at ?? t('recommendationPage.notCompleted')}
            </dd>
          </div>
        </dl>
      </Card>

      <Section label={t('recommendationPage.briefSection')}>
        <Card>
          {briefEntries.length > 0 ? (
            <details>
              <summary className="cursor-pointer text-2xs font-semibold text-accent list-none [&::-webkit-details-marker]:hidden">
                {t('recommendationPage.briefToggle')}
              </summary>
              <dl className="m-0 mt-2 flex flex-col gap-1">
                {briefEntries.map((e) => (
                  <div key={e.key} className="flex flex-wrap gap-2 text-2xs">
                    <dt className="font-semibold text-ink-3">{e.key}</dt>
                    <dd className="m-0 max-w-prose text-ink-2">{e.value}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ) : (
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.briefEmpty')}</p>
          )}
        </Card>
      </Section>

      <Section label={t('recommendationPage.transcriptSection')}>
        {rounds.length > 0 ? (
          <div className="flex flex-col gap-4">
            {rounds.map((r) => (
              <Card key={r.round}>
                <h3 className="m-0 text-2xs font-bold text-ink-2">
                  {t('recommendation.transcriptRound', { n: r.round })}
                </h3>
                <ul className="m-0 flex list-none flex-col gap-3 p-0">
                  {r.turns.map((turn, i) => (
                    <li key={i} className="flex flex-col gap-1 text-xs">
                      <span className="font-semibold text-ink">{roleLabel(t, turn.agent_role)}</span>
                      <span className="max-w-prose text-ink-2">{turn.content}</span>
                      {turn.evidence_cited.length > 0 ? (
                        <ul className="m-0 flex list-none flex-col gap-0.5 p-0 ps-3">
                          {turn.evidence_cited.map((e, j) => (
                            <li key={j} className="text-2xs text-ink-3">
                              — {e}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-2xs text-ink-3">{t('recommendation.evidenceNone')}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.transcriptEmpty')}</p>
          </Card>
        )}
      </Section>

      <Section label={t('recommendationPage.verdictsSection')}>
        <Card>
          {rec.verdicts.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {rec.verdicts.map((v, i) => (
                <li key={i} className="flex flex-col gap-1 text-xs">
                  <span>
                    <span className="font-semibold">{t('recommendation.judgeLabel')}</span>{' '}
                    {t(`recommendation.verdict.${v.verdict}`)} — {v.reasoning}
                  </span>
                  {v.evidence_cited.length > 0 ? (
                    <ul className="m-0 flex list-none flex-col gap-0.5 p-0 ps-3">
                      {v.evidence_cited.map((e, j) => (
                        <li key={j} className="text-2xs text-ink-3">
                          — {e}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.verdictsEmpty')}</p>
          )}
        </Card>
      </Section>

      <Section label={t('recommendationPage.resultSection')}>
        <Card>
          {failedMessage ? (
            <p role="alert" className="m-0 text-xs font-semibold text-risk-critical">
              {failedMessage}
            </p>
          ) : parsed ? (
            <div className="flex flex-col gap-3">
              <p className="m-0 max-w-prose text-sm leading-relaxed text-ink">{parsed.body}</p>
              {parsed.contested ? (
                <p className="m-0 max-w-prose rounded-card border-s-4 border-risk-moderate bg-surface-2 p-3 text-2xs text-ink-2">
                  {t('recommendation.contestedNote', { reasoning: parsed.contested })}
                </p>
              ) : null}
              <p className="m-0 text-2xs text-ink-3">
                {rec.converged
                  ? t('recommendation.convergedYes', { rounds: rec.rounds_used, max: MAX_ROUNDS })
                  : t('recommendation.convergedNo', { max: MAX_ROUNDS })}
              </p>
            </div>
          ) : (
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.resultNone')}</p>
          )}
        </Card>
      </Section>

      <Section label={t('recommendationPage.limitationsSection')}>
        <Card>
          {rec.gaps.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {rec.gaps.map((g, i) => (
                <li key={i} className="flex items-start gap-2 text-2xs text-ink-2">
                  {g.severity ? (
                    <span className={`mt-0.5 inline-block shrink-0 border px-1 py-0.5 text-2xs ${BAND_CLASS[GAP_BAND[g.severity]]}`}>
                      {t(`common:hazard.${GAP_BAND[g.severity]}`)}
                    </span>
                  ) : null}
                  <span className="max-w-prose">{g.gap_description}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.limitationsEmpty')}</p>
          )}
        </Card>
      </Section>

      <Section label={t('recommendationPage.evidenceSection')}>
        <Card>
          {evidenceAll.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {evidenceAll.map((e, i) => (
                <li key={i} className="text-2xs text-ink-2">
                  — {e}
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-2xs text-ink-3">{t('recommendationPage.evidenceEmpty')}</p>
          )}
        </Card>
      </Section>
    </PageShell>
  );
}
