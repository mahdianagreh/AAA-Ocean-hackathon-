import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type { RouteName } from './useRoute';

/** Drives the browser tab title from the route.
 *
 *  Phase 7 flagged that document.title was pinned to the brand on every page, so
 *  a judge with eight tabs open could not tell them apart. Each route now sets
 *  "<page> · AQABA AQUA AI", in the active language, except the marketing home
 *  which is the brand alone. The in-page H1 is already per-page via PageShell;
 *  this is only the tab.
 *
 *  The brand string is fixed artwork, never translated — Montserrat is Latin-only
 *  and the wordmark is the same in both locales. */
const BRAND = 'AQABA AQUA AI';

/** Route → nav-namespace key. reefZone (detail) borrows the index label. Routes
 *  whose pages arrive later (systemHealth, dataExplorer, journey) are added here
 *  when they land. Anything absent falls back to the brand alone. */
const TITLE_KEY: Partial<Record<RouteName, string>> = {
  dashboard: 'overview',
  events: 'events',
  replay: 'replay',
  reefZones: 'reefZones',
  reefZone: 'reefZones',
  alerts: 'alerts',
  reports: 'reports',
  assistant: 'assistant',
  validation: 'validation',
  provenance: 'provenance',
  sitesScore: 'sites',
  limitations: 'limitations',
  systemHealth: 'systemHealth',
  dataExplorer: 'dataExplorer',
  account: 'account',
  login: 'login',
  signup: 'signup',
  notFound: 'notFound',
};

export function useDocumentTitle(routeName: RouteName) {
  const { t, i18n } = useTranslation('nav');

  useEffect(() => {
    const key = TITLE_KEY[routeName];
    document.title = key ? `${t(key)} · ${BRAND}` : BRAND;
  }, [routeName, t, i18n.language]);
}
