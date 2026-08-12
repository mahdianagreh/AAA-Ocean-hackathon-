import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Popover } from 'radix-ui';
import type { RecommendationTurn, RecommendationVerdict, ResponseRecommendation } from '../api/live';
import { MAX_ROUNDS, SWARM_FAILED_PREFIX, roleLabel } from '../app/recommendationText';

/** Phase 9's debate visualisation — five specialists and the judge seated
 *  around a table, replacing the round-by-round transcript's full paragraphs
 *  with one caption per seat (the requested redesign: "small caption is
 *  enough… shows on which iteration it is… make it interactive").
 *
 *  A seat always shows its OWN latest statement, not a frozen round-1 one — as
 *  rounds land, the caption cross-fades to whatever that role said most
 *  recently (`animate-caption-swap`, keyed on round+content so it only plays
 *  on a real change). Nothing here invents a shorter sentence: the caption is
 *  the model's own text, cut at a word boundary — the full text is one tap
 *  away in a Popover, never lost, matching this project's "small caption,
 *  interactive" instruction rather than "less information."
 *
 *  Positions are fixed angles round a six-seat table (judge at the head, five
 *  specialists spaced 60° apart) — not computed from N, because N is always 6
 *  here (the roster is fixed, tasks/phase9/00-phase9-plan.md §5) and a
 *  general N-seat layout would be a speculative abstraction for a table that
 *  never seats anyone else.
 */

const JUDGE = 'judge';

// (angleDeg, role) — -90° is the top of the table (12 o'clock), clockwise from
// there. Judge presides at the head; the five specialists take the other five
// hours of a six-seat clock face.
const SEATS: ReadonlyArray<{ angleDeg: number; role: string; judge?: boolean }> = [
  { angleDeg: -90, role: JUDGE, judge: true },
  { angleDeg: -30, role: 'aseza' },
  { angleDeg: 30, role: 'marine_science' },
  { angleDeg: 90, role: 'port_ops' },
  { angleDeg: 150, role: 'civil_defense' },
  { angleDeg: 210, role: 'tourism' },
];

const RX = 42; // ellipse radii, percent of the table container
const RY = 38;
const CAPTION_MAX = 88;

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

function latestTurnByRole(turns: RecommendationTurn[]): Map<string, RecommendationTurn> {
  const out = new Map<string, RecommendationTurn>();
  for (const turn of turns) {
    const prev = out.get(turn.agent_role);
    if (!prev || turn.round > prev.round) out.set(turn.agent_role, turn);
  }
  return out;
}

function SeatDot({ state }: { state: 'waiting' | 'spoke' | 'judge' }) {
  const cls =
    state === 'judge' ? 'bg-accent' : state === 'spoke' ? 'bg-risk-low' : 'bg-ink-3';
  return <span className={`inline-block size-1.5 rounded-full ${cls} ${state === 'waiting' ? 'aq-pulse' : ''}`} />;
}

export function DebateTable({ rec }: { rec: ResponseRecommendation }) {
  const { t } = useTranslation('pages');
  const [openSeat, setOpenSeat] = useState<string | null>(null);

  const currentRound = Math.max(0, ...rec.turns.map((turn) => turn.round));
  const running = !rec.completed_at;
  const failed = rec.final_recommendation?.startsWith(SWARM_FAILED_PREFIX) ?? false;
  const latest = latestTurnByRole(rec.turns);
  const latestVerdict: RecommendationVerdict | undefined = rec.verdicts[rec.verdicts.length - 1];

  return (
    <div
      className="relative mx-auto aspect-[16/11] w-full max-w-2xl"
      data-component="debate-table"
    >
      {/* The table's physical surface — a padded rail around a sunken felt,
          decorative only (aria-hidden), giving the seats something to sit
          "around" rather than float in empty space. Two layers so the rail
          reads as raised and the felt as recessed, the way a real card table
          is built. */}
      <div aria-hidden="true" className="table-rail absolute rounded-[50%]" style={{ inset: '13%' }} />
      <div aria-hidden="true" className="table-felt absolute rounded-[50%]" style={{ inset: '19%' }} />

      {/* Center medallion: round counter while running, verdict on completion.
          A raised chip on the felt, not felt-coloured text — its own opaque
          card so ink/risk tokens keep their normal light/dark contrast
          regardless of the fixed-dark felt underneath. Its own element is
          swapped (not restyled in place) so the reveal animation plays
          exactly once, the moment the swarm finishes. */}
      <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-full bg-surface px-4 py-3 text-center shadow-lg">
        {rec.completed_at ? (
          <div
            key="done"
            className="animate-verdict-reveal flex flex-col items-center gap-1"
          >
            <span
              className={`rounded-full border px-2.5 py-1 text-2xs font-bold ${
                failed || latestVerdict?.verdict === 'rejected'
                  ? 'border-risk-high text-risk-high'
                  : 'border-risk-low text-risk-low'
              }`}
            >
              {failed
                ? t('recommendation.table.failed')
                : latestVerdict
                  ? t(`recommendation.verdict.${latestVerdict.verdict}`)
                  : t('recommendation.table.done')}
            </span>
            {!failed ? (
              <span className="text-2xs text-ink-3">
                {rec.converged
                  ? t('recommendation.convergedYes', { rounds: rec.rounds_used, max: MAX_ROUNDS })
                  : t('recommendation.convergedNo', { max: MAX_ROUNDS })}
              </span>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1">
            <span className="flex items-center gap-1.5 text-xs font-bold text-ink" aria-live="polite">
              <SeatDot state="waiting" />
              {currentRound > 0
                ? t('recommendation.table.roundBadge', { round: currentRound, max: MAX_ROUNDS })
                : t('recommendation.table.starting')}
            </span>
          </div>
        )}
      </div>

      {SEATS.map((seat, i) => {
        const angle = (seat.angleDeg * Math.PI) / 180;
        const left = 50 + RX * Math.cos(angle);
        const top = 50 + RY * Math.sin(angle);

        const turn = seat.judge ? undefined : latest.get(seat.role);
        const spoke = seat.judge ? Boolean(latestVerdict) : Boolean(turn);
        const captionSource = seat.judge ? latestVerdict?.reasoning : turn?.content;
        const caption = captionSource
          ? truncate(captionSource, CAPTION_MAX)
          : seat.judge
            ? t('recommendation.table.awaitingJudge')
            : t('recommendation.table.waiting');
        const captionKey = seat.judge ? `${rec.verdicts.length}` : `${turn?.round ?? 0}:${turn?.content ?? ''}`;

        return (
          <Popover.Root
            key={seat.role}
            open={openSeat === seat.role}
            onOpenChange={(o) => setOpenSeat(o ? seat.role : null)}
          >
            <Popover.Trigger asChild>
              <button
                type="button"
                disabled={!spoke && !seat.judge}
                className={`animate-seat-in absolute flex w-32 -translate-x-1/2 -translate-y-1/2 flex-col gap-1 rounded-card border p-2.5 text-start transition-colors sm:w-36 ${
                  seat.judge
                    ? 'border-accent bg-surface glass-panel shadow-md hover:shadow-lg'
                    : spoke
                      ? 'border-hairline bg-surface shadow-sm hover:border-accent hover:shadow-md'
                      : 'border-dashed border-hairline bg-surface/60'
                } ${spoke || seat.judge ? 'cursor-pointer' : 'cursor-default'}`}
                style={
                  { left: `${left}%`, top: `${top}%`, '--seat-delay': `${i * 70}ms` } as CSSProperties
                }
              >
                <span className="flex items-center gap-1.5 text-2xs font-bold uppercase tracking-wide text-ink-2">
                  <SeatDot state={seat.judge ? 'judge' : spoke ? 'spoke' : 'waiting'} />
                  {seat.judge ? t('recommendation.table.judge') : roleLabel(t, seat.role)}
                </span>
                <span key={captionKey} className="animate-caption-swap line-clamp-2 text-2xs text-ink-2">
                  {caption}
                </span>
              </button>
            </Popover.Trigger>
            {(spoke || seat.judge) ? (
              <Popover.Portal>
                <Popover.Content
                  sideOffset={8}
                  className="z-50 max-w-sm rounded-card glass-card p-4 text-xs shadow-2xl data-[state=open]:animate-content-show"
                >
                  <p className="m-0 mb-2 text-2xs font-bold uppercase tracking-wide text-ink-2">
                    {seat.judge ? t('recommendation.table.judge') : roleLabel(t, seat.role)}
                  </p>
                  {seat.judge ? (
                    rec.verdicts.length > 0 ? (
                      <ul className="m-0 flex list-none flex-col gap-2 p-0">
                        {rec.verdicts.map((v, vi) => (
                          <li key={vi} className="flex flex-col gap-1">
                            <span className="text-2xs font-semibold text-ink">
                              {t(`recommendation.verdict.${v.verdict}`)}
                            </span>
                            <span className="max-w-prose text-ink-2">{v.reasoning}</span>
                            {v.evidence_cited.length > 0 ? (
                              <ul className="m-0 flex list-none flex-col gap-0.5 p-0 ps-3">
                                {v.evidence_cited.map((e, ei) => (
                                  <li key={ei} className="text-2xs text-ink-3">
                                    — {e}
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="m-0 text-ink-3">{t('recommendation.table.awaitingJudge')}</p>
                    )
                  ) : (
                    <div className="flex flex-col gap-2">
                      <p className="m-0 max-w-prose text-ink-2">{turn?.content}</p>
                      {turn && turn.evidence_cited.length > 0 ? (
                        <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
                          {turn.evidence_cited.map((e, ei) => (
                            <li key={ei} className="text-2xs text-ink-3">
                              — {e}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-2xs text-ink-3">{t('recommendation.evidenceNone')}</span>
                      )}
                      <span className="text-2xs text-ink-3">
                        {t('recommendation.table.spokenInRound', { round: turn?.round ?? 0 })}
                      </span>
                    </div>
                  )}
                  <Popover.Arrow className="fill-surface" />
                </Popover.Content>
              </Popover.Portal>
            ) : null}
          </Popover.Root>
        );
      })}
      <span className="sr-only" aria-live="polite">
        {running
          ? t('recommendation.table.liveRegionRunning', { round: currentRound, max: MAX_ROUNDS })
          : t('recommendation.table.liveRegionDone')}
      </span>
    </div>
  );
}
