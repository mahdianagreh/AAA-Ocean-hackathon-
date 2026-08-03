import { useTranslation } from 'react-i18next';
import { CatchmentGlyph, OutletGlyph, ReefZoneGlyph } from '../icons';
import { useUi } from '../app/uiStore';
import { specimenEnabled } from '../app/useRoute';

/** Phase 0 placeholder.
 *
 *  The real layout regions — masthead, map, side rail, scenario drawer, time
 *  bar, overlays — land in Phase 1 with the map. This exists so the token layer,
 *  the fonts, the language switch and the theme switch are all provably working
 *  on `/` and not only inside the specimen iframes.
 *
 *  Deliberately not a fake dashboard. 00's risk register lists "dashboard
 *  becomes more important than science", and a mocked-up map here would be the
 *  first step toward exactly that.
 */
export function Home() {
  const { t } = useTranslation();
  const { theme, lang, setTheme, setLang } = useUi();

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 p-6">
      <header className="flex flex-col gap-2 border-b border-hairline pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="flex items-baseline gap-2 text-xl font-semibold">
            <span dir="ltr" style={{ unicodeBidi: 'isolate' }}>
              {t('brand.name')}
            </span>
            <span className="text-md font-normal text-ink-2">{t('brand.place')}</span>
          </h1>

          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-2">
              <span className="text-ink-2">{t('chrome.language')}</span>
              <select
                className="rule bg-surface px-2 py-1 text-ink"
                value={lang}
                onChange={(e) => setLang(e.target.value === 'ar' ? 'ar' : 'en')}
              >
                <option value="en">English</option>
                <option value="ar">العربية</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-ink-2">{t('chrome.theme')}</span>
              <select
                className="rule bg-surface px-2 py-1 text-ink"
                value={theme}
                onChange={(e) => setTheme(e.target.value as 'light' | 'dark' | 'system')}
              >
                <option value="system">{t('chrome.themeSystem')}</option>
                <option value="light">{t('chrome.themeLight')}</option>
                <option value="dark">{t('chrome.themeDark')}</option>
              </select>
            </label>
          </div>
        </div>
        <p className="text-sm text-ink-2">{t('brand.tagline')}</p>
      </header>

      <section className="flex flex-wrap gap-6">
        {(
          [
            [CatchmentGlyph, 'catchment'],
            [OutletGlyph, 'outlet'],
            [ReefZoneGlyph, 'reefZone'],
          ] as const
        ).map(([Icon, key]) => (
          <div key={key} className="flex items-center gap-3 rule px-4 py-3">
            <Icon size={24} label={t(`glyph.${key}`)} />
            <span className="text-sm">{t(`glyph.${key}`)}</span>
          </div>
        ))}
      </section>

      <footer className="mt-auto border-t border-hairline pt-4 text-xs text-ink-3">
        Phase 0 — language lock. The map, its layers and the three modes land in Phase 1.
        {specimenEnabled ? (
          <>
            {' '}
            <a className="text-accent underline" href="/specimen">
              /specimen
            </a>{' '}
            renders every component in both themes × both directions.
          </>
        ) : null}
      </footer>
    </main>
  );
}
