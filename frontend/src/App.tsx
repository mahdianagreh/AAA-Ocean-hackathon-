import { Direction } from 'radix-ui';
import { useDocumentChrome } from './app/useDocumentChrome';
import { specimenEnabled, useRoute } from './app/useRoute';
import { DashboardChrome } from './shell/DashboardChrome';
import { Dashboard } from './routes/Dashboard';
import { Landing } from './routes/Landing';
import { Login } from './routes/Login';
import { Signup } from './routes/Signup';
import { AlertsPage } from './routes/AlertsPage';
import { EventsPage } from './routes/EventsPage';
import { ReplayPage } from './routes/ReplayPage';
import { ReefZonesPage } from './routes/ReefZonesPage';
import { ReefZonePage } from './routes/ReefZonePage';
import { ReportsPage } from './routes/ReportsPage';
import { SiteScorePage } from './routes/SiteScorePage';
import { AccountPage } from './routes/AccountPage';
import { AssistantPage } from './routes/AssistantPage';
import { ValidationPage } from './routes/ValidationPage';
import { ProvenancePage } from './routes/ProvenancePage';
import { LimitationsPage } from './routes/LimitationsPage';
import { NotFoundPage } from './routes/NotFoundPage';
import { Specimen } from './routes/Specimen';
import { SpecimenSolo } from './routes/SpecimenSolo';
import { BacktestsPage } from './routes/BacktestsPage';
import { SystemHealthPage } from './routes/SystemHealthPage';
import { DataExplorerPage } from './routes/DataExplorerPage';

export function App() {
  const route = useRoute();
  const { dir } = useDocumentChrome();
  const solo = new URLSearchParams(window.location.search).get('solo') === '1';

  /** DirectionProvider is mandatory, not belt-and-braces.
   *
   *  Verified in the installed source: Radix's useDirection is
   *  `localDir || React.useContext(DirectionContext) || 'ltr'` — it reads a
   *  context and never touches the DOM. So without this provider, Slider
   *  arrow-key semantics, Menu and Select popper alignment, and ScrollArea all
   *  compute LTR under <html dir="rtl">. 00's risk register asks for
   *  per-primitive RTL checks; every one of them would fail here for the same
   *  single reason, while looking like five separate bugs. */
  return (
    <Direction.DirectionProvider dir={dir}>
      {renderRoute()}
    </Direction.DirectionProvider>
  );

  function renderRoute() {
    switch (route.name) {
      // Marketing and auth sit outside the dashboard chrome — they have their
      // own nav, and the navy rail would be nonsense on a signed-out page.
      case 'home':
        return <Landing />;
      case 'login':
        return <Login />;
      case 'signup':
        return <Signup />;

      case 'specimen':
        if (!specimenEnabled) return <NotFoundPage />;
        return solo ? <SpecimenSolo /> : <Specimen />;

      // The map screen brings its own full-height grid, so it is wrapped but
      // not padded — see DashboardChrome, which only supplies the rail.
      case 'dashboard':
        return (
          <DashboardChrome>
            <Dashboard />
          </DashboardChrome>
        );

      case 'replay':
        return (
          <DashboardChrome>
            <ReplayPage eventId={route.params.eventId} />
          </DashboardChrome>
        );
      case 'reefZone':
        return (
          <DashboardChrome>
            <ReefZonePage zoneId={route.params.id} />
          </DashboardChrome>
        );

      case 'alerts':
        return wrap(<AlertsPage />);
      case 'events':
        return wrap(<EventsPage />);
      case 'reefZones':
        return wrap(<ReefZonesPage />);
      case 'reports':
        return wrap(<ReportsPage />);
      case 'sitesScore':
        return wrap(<SiteScorePage />);
      case 'account':
        return wrap(<AccountPage />);
      case 'assistant':
        return wrap(<AssistantPage />);
      case 'validation':
        return wrap(<ValidationPage />);
      case 'provenance':
        return wrap(<ProvenancePage />);
      case 'limitations':
        return wrap(<LimitationsPage />);
      case 'backtests':
        return wrap(<BacktestsPage />);
      case 'system':
        return wrap(<SystemHealthPage />);
      case 'explorer':
        return wrap(<DataExplorerPage />);

      default:
        return <NotFoundPage />;
    }
  }

  function wrap(node: React.ReactNode) {
    return <DashboardChrome>{node}</DashboardChrome>;
  }
}
