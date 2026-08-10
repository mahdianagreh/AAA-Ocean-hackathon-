import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { LogoMark } from '../components/Logo';
import { AssistantDock } from '../components/AssistantDock';
import { useRoute, type RouteName } from '../app/useRoute';
import { useAuth } from '../app/AuthContext';
import { navigate } from '../app/useRoute';

/** The dashboard navigation rail.
 *
 *  The rail is Deep Navy in both themes because it is brand furniture rather
 *  than a data surface — see --brand-navy in theme.css. That means nothing
 *  inside it may use --ink or --canvas, which invert; it is always light-on-dark,
 *  and the contrast pairs are fixed and checked against the brand palette
 *  (foam #E6F7FA on navy #0A1F4D is 14.6:1) rather than against the theme.
 *
 *  Every destination here is a real route. Four of the five overlay panels that
 *  used to be modal-only (validation, provenance, limitations, assistant) now
 *  have URLs too, so a judge can be sent straight to one — but OverlayHost still
 *  works, because the map screen's own buttons still open them in place. The
 *  fifth, the 3D Journey, is deliberately map-overlay-only: it needs the live
 *  terrain/plume context of the map screen and does not stand alone at a URL. */

interface NavItem {
  to: string;
  labelKey: string;
  match: RouteName[];
  icon: ReactNode;
}

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

/** Outline icons, 2px-ish stroke, minimal geometric — brand guidelines §10.
 *  currentColor throughout so the active/idle states need no icon variants. */
const ICONS: Record<string, ReactNode> = {
  overview: (
    <>
      <rect x="2.5" y="2.5" width="5" height="5" {...stroke} />
      <rect x="9.5" y="2.5" width="4" height="4" {...stroke} />
      <rect x="2.5" y="9.5" width="4" height="4" {...stroke} />
      <rect x="9.5" y="9.5" width="4" height="4" {...stroke} />
    </>
  ),
  forecast: (
    <>
      <circle cx="8" cy="8" r="5.5" {...stroke} />
      <path d="M8 4.5 L8 8 L10.5 9.5" {...stroke} />
    </>
  ),
  replay: <path d="M2 11 Q5 5 8 11 Q11 17 14 11" {...stroke} />,
  reef: <path d="M8 2.5 L14 13.5 L2 13.5 Z" {...stroke} />,
  alerts: (
    <>
      <path d="M8 2.5 L14.5 13.5 L1.5 13.5 Z" {...stroke} />
      <path d="M8 6.5 L8 9.5" {...stroke} />
      <circle cx="8" cy="11.6" r="0.7" fill="currentColor" />
    </>
  ),
  events: (
    <>
      <rect x="2.5" y="3" width="11" height="10.5" {...stroke} />
      <path d="M2.5 6.5 H13.5 M5.5 3 V1.5 M10.5 3 V1.5" {...stroke} />
    </>
  ),
  reports: (
    <>
      <rect x="3" y="2" width="10" height="12" {...stroke} />
      <path d="M5.5 6 H10.5 M5.5 9 H10.5 M5.5 11.5 H8.5" {...stroke} />
    </>
  ),
  assistant: (
    <>
      <circle cx="8" cy="8" r="5.5" {...stroke} />
      <path d="M6.4 6.3 A1.7 1.7 0 1 1 8 9 V10" {...stroke} />
      <circle cx="8" cy="11.8" r="0.6" fill="currentColor" />
    </>
  ),
  validation: (
    <>
      <path d="M2 12.5 L6 7.5 L9 10 L14 3.5" {...stroke} />
      <path d="M2 14 H14" {...stroke} />
    </>
  ),
  provenance: (
    <>
      <rect x="2.5" y="2.5" width="11" height="11" {...stroke} />
      <path d="M2.5 10 L6 6.5 L9 9.5 L13.5 5" {...stroke} />
    </>
  ),
  sites: (
    <>
      <path d="M8 14 S13 9.5 13 6.5 A5 5 0 0 0 3 6.5 C3 9.5 8 14 8 14 Z" {...stroke} />
      <circle cx="8" cy="6.5" r="1.8" {...stroke} />
    </>
  ),
  limits: <path d="M2 13.5 L2 8.5 L8 3.5 L14 8.5 L14 13.5 Z" {...stroke} />,
  backtests: <path d="M8 2.5 A 5.5 5.5 0 1 0 13.5 8 M8 5 V8 L10.5 9.5" {...stroke} />,
  systemHealth: <path d="M1.5 8 H5 L6.5 4 L9 12 L10.5 8 H14.5" {...stroke} />,
  dataExplorer: (
    <>
      <ellipse cx="8" cy="4" rx="5.5" ry="2" {...stroke} />
      <path d="M2.5 4 V12 C2.5 13.1 5 14 8 14 C11 14 13.5 13.1 13.5 12 V4" {...stroke} />
      <path d="M2.5 8 C2.5 9.1 5 10 8 10 C11 10 13.5 9.1 13.5 8" {...stroke} />
    </>
  ),
};

const NAV: NavItem[] = [
  { to: '/dashboard', labelKey: 'overview', match: ['dashboard'], icon: ICONS.overview },
  { to: '/events', labelKey: 'events', match: ['events'], icon: ICONS.events },
  { to: '/dashboard/replay', labelKey: 'replay', match: ['replay'], icon: ICONS.replay },
  { to: '/reef-zones', labelKey: 'reefZones', match: ['reefZones', 'reefZone'], icon: ICONS.reef },
  { to: '/alerts', labelKey: 'alerts', match: ['alerts'], icon: ICONS.alerts },
  { to: '/reports', labelKey: 'reports', match: ['reports'], icon: ICONS.reports },
  { to: '/assistant', labelKey: 'assistant', match: ['assistant'], icon: ICONS.assistant },
  { to: '/dashboard/validation', labelKey: 'validation', match: ['validation'], icon: ICONS.validation },
  { to: '/dashboard/provenance', labelKey: 'provenance', match: ['provenance'], icon: ICONS.provenance },
  { to: '/sites/score', labelKey: 'sites', match: ['sitesScore'], icon: ICONS.sites },
  { to: '/limitations', labelKey: 'limitations', match: ['limitations'], icon: ICONS.limits },
  { to: '/backtests', labelKey: 'backtests', match: ['backtests'], icon: ICONS.backtests },
  { to: '/system-health', labelKey: 'systemHealth', match: ['systemHealth'], icon: ICONS.systemHealth },
  { to: '/data-explorer', labelKey: 'dataExplorer', match: ['dataExplorer'], icon: ICONS.dataExplorer },
];

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const { t } = useTranslation('nav');
  return (
    <Link
      to={item.to}
      data-nav={item.labelKey}
      aria-current={active ? 'page' : undefined}
      className="flex items-center gap-3 rounded-sm px-3 py-2.5 text-xs font-semibold no-underline"
      style={{
        color: active ? '#fff' : 'var(--brand-foam)', // token-ok: fixed brand rail
        background: active ? 'rgb(255 255 255 / 0.14)' : 'transparent',
        // Active state is not carried by colour alone — 09 rule 5. The inline
        // start edge gets an aqua marker that survives greyscale and CVD.
        boxShadow: active ? 'inset 3px 0 0 0 var(--brand-aqua)' : 'none',
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        {item.icon}
      </svg>
      <span>{t(item.labelKey)}</span>
    </Link>
  );
}

export function DashboardChrome({ children }: { children: ReactNode }) {
  const { t } = useTranslation('nav');
  const route = useRoute();
  const { session, signOut, sessionExpired, clearSessionExpired } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink lg:flex-row" data-dash-shell="true">
      <nav
        aria-label={t('primary')}
        className="flex shrink-0 flex-col gap-7 px-5 py-7 lg:w-60 lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto"
        style={{ background: 'var(--brand-navy)' }}
      >
        <Link to="/" className="flex items-center gap-2.5 no-underline">
          <LogoMark size={26} variant="white" />
          <span
            dir="ltr"
            className="text-xs font-bold"
            style={{ letterSpacing: '0.06em', color: '#fff' }} // token-ok: fixed brand rail
          >
            AQABA AQUA AI
          </span>
        </Link>

        {/* Horizontal wrap below lg so eleven destinations do not become a tall
            navy column that buries the content on a phone; a vertical rail at lg. */}
        <div className="flex flex-row flex-wrap gap-1 lg:flex-col">
          {NAV.map((item) => (
            <NavLink key={item.to} item={item} active={item.match.includes(route.name)} />
          ))}
        </div>

        <div
          className="mt-auto flex flex-col gap-2 pt-4 sticky bottom-0 z-10"
          style={{ 
            borderBlockStart: '1px solid rgb(255 255 255 / 0.15)',
            background: 'var(--brand-navy)',
            paddingBottom: '1.75rem',
            marginBottom: '-1.75rem'
          }}
        >
          {/* Phase 8, Track B: only says "signed in as" when a real verified
              session exists — the same claim would have been a lie before
              this. Reads (this whole dashboard) stay open either way, per
              tasks/00-contracts.md §9 — signing out never adds a login wall. */}
          {session ? (
            <span className="text-2xs" style={{ color: 'var(--brand-foam)', opacity: 0.7 }}>
              {t('signedInAs', { email: session.user.email })}
            </span>
          ) : (
            <span className="text-2xs" style={{ color: 'var(--brand-foam)', opacity: 0.7 }}>
              {t('accessMode')}
            </span>
          )}
          <Link
            to="/account"
            className="text-2xs no-underline"
            style={{ color: 'var(--brand-aqua)' }}
          >
            {t('account')}
          </Link>
          {session ? (
            <button
              type="button"
              onClick={() => {
                void signOut().then(() => navigate('/'));
              }}
              className="text-2xs no-underline text-start"
              style={{ color: 'var(--brand-aqua)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
            >
              {t('signOut')}
            </button>
          ) : (
            <Link to="/login" className="text-2xs no-underline" style={{ color: 'var(--brand-aqua)' }}>
              {t('signIn')}
            </Link>
          )}
          <Link to="/" className="text-2xs no-underline" style={{ color: 'var(--brand-aqua)' }}>
            {t('backToSite')}
          </Link>
        </div>
      </nav>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* A refresh failed silently in the background — AuthContext tells this
            apart from an explicit sign-out. Reads stay open either way
            (tasks/00-contracts.md §9), so this is a dismissible notice, not a
            login wall: the only thing that changed is that "signed in as..."
            in the rail below is no longer true. */}
        {sessionExpired ? (
          <div
            role="status"
            className="flex items-center justify-between gap-3 border-b-2 border-risk-high-stroke bg-surface-2 px-4 py-2"
          >
            <p className="m-0 flex items-center gap-2 text-xs text-ink">
              <span aria-hidden="true" className="text-risk-high">⚠</span>
              {t('sessionExpired')}
            </p>
            <button
              type="button"
              onClick={clearSessionExpired}
              className="shrink-0 text-2xs font-semibold text-accent hover:underline"
            >
              {t('sessionExpiredDismiss')}
            </button>
          </div>
        ) : null}
        {children}
      </div>

      {/* Persistent assistant surface on every dashboard page except the
          assistant page (redundant) and the map (its masthead carries it). */}
      {route.name !== 'assistant' && route.name !== 'dashboard' ? <AssistantDock /> : null}
    </div>
  );
}
