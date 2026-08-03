import { Direction } from 'radix-ui';
import { useDocumentChrome } from './app/useDocumentChrome';
import { specimenEnabled, useRoute } from './app/useRoute';
import { Home } from './routes/Home';
import { Specimen } from './routes/Specimen';
import { SpecimenSolo } from './routes/SpecimenSolo';

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
   *  compute LTR even under <html dir="rtl">. 00's risk register asks for
   *  per-primitive RTL checks; every one of them would fail here for the same
   *  single reason, while looking like five separate bugs. */
  return (
    <Direction.DirectionProvider dir={dir}>
      {route === '/specimen' && specimenEnabled ? (
        solo ? (
          <SpecimenSolo />
        ) : (
          <Specimen />
        )
      ) : (
        <Home />
      )}
    </Direction.DirectionProvider>
  );
}
