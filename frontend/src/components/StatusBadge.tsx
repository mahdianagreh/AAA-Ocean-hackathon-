/** A status badge that cannot be styled away.
 *
 *  Three uses across Pulga's screens:
 *  - Report status:     ai_drafted / human_reviewed
 *  - Sensitivity weight: IN USE / NOT IN USE
 *  - Adaptive sampling: NO_FEEDBACK_YET / FEEDBACK_APPLIED
 *
 *  Form + text, never colour alone. Takes no className prop — the whole point
 *  is that nothing outside this component can shrink or mute it. */

export type BadgeVariant =
  | 'ai_drafted'
  | 'human_reviewed'
  | 'in_use'
  | 'not_in_use'
  | 'no_feedback'
  | 'feedback_applied';

const STYLES: Record<BadgeVariant, string> = {
  ai_drafted:
    'border-risk-high-stroke text-risk-high-on bg-surface-2',
  human_reviewed:
    'border-data-measured text-data-measured bg-surface',
  in_use:
    'border-hairline text-ink-2 bg-surface-2',
  not_in_use:
    'border-risk-high-stroke text-risk-high-on bg-surface-2 border-dashed',
  no_feedback:
    'border-hairline text-ink-3 bg-surface-2',
  feedback_applied:
    'border-data-modelled text-data-modelled bg-surface',
};

const LABELS: Record<BadgeVariant, string> = {
  ai_drafted: 'AI DRAFTED',
  human_reviewed: 'HUMAN REVIEWED',
  in_use: 'IN USE',
  not_in_use: 'NOT IN USE',
  no_feedback: 'NO FEEDBACK YET',
  feedback_applied: 'FEEDBACK APPLIED',
};

export function StatusBadge({ variant }: { variant: BadgeVariant }) {
  return (
    <span
      className={`inline-block w-fit border px-1.5 py-0.5 text-2xs font-semibold ${STYLES[variant]}`}
      data-status-badge={variant}
    >
      {LABELS[variant]}
    </span>
  );
}
