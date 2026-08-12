import type { RecommendationTurn } from '../api/live';
import type { HazardBand } from '../api/types';

/** Shared parsing/labelling for the "Recommended Response" swarm
 *  (Phase 9), used by both the inline `RecommendedResponsePanel` (on an
 *  alert card) and the full-page `RecommendationPage`. Kept here, not
 *  duplicated, because both consumers must agree on what a role/gap/verdict
 *  string actually means. */

/** The swarm always runs at most 3 rounds (Phase 9 §3) — not derived from any
 *  response field, so both the panel and the full page must agree on it. */
export const MAX_ROUNDS = 3;

export const ROLE_KEYS: readonly RecommendationTurn['agent_role'][] = [
  'aseza',
  'marine_science',
  'port_ops',
  'civil_defense',
  'tourism',
];

export const GAP_BAND: Record<'low' | 'medium' | 'high', HazardBand> = {
  low: 'low',
  medium: 'moderate',
  high: 'high',
};

export const SWARM_FAILED_PREFIX = '[swarm failed:';
const CONTESTED_RE = /^\[APPROVED WITH CAVEAT — contested by judge after revision: (.+?)\] ([\s\S]*)$/;

export function parseFinal(text: string): { body: string; contested: string | null } {
  const m = CONTESTED_RE.exec(text);
  if (!m) return { body: text, contested: null };
  return { contested: m[1], body: m[2] };
}

export function roleLabel(t: (k: string) => string, role: string): string {
  return ROLE_KEYS.includes(role) ? t(`recommendation.role.${role}`) : role;
}
