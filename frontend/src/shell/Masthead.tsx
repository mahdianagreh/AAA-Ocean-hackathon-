import { useTranslation } from 'react-i18next';
import { useUi, type Lang, type ThemeChoice } from '../app/uiStore';
import { DATA_SOURCE } from '../api';
import { ConnectionState } from './ConnectionState';

/** Masthead: brand, mode switcher, language toggle, connection state — 03 §3.
 *
 *  The mode switcher is Phase 2 (it needs a time cursor to preserve), so the
 *  three modes are shown disabled rather than absent. A control that appears in
 *  Phase 2 changes the layout; a disabled one does not.
 */
export function Masthead() {
  const { t } = useTranslation();
  const { theme, lang, setTheme, setLang } = useUi();

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline bg-surface px-4 py-2">
      <div className="flex items-baseline gap-2">
        <h1 className="text-md font-semibold">
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }}>
            {t('brand.name')}
          </span>
        </h1>
        <span className="text-xs text-ink-2">{t('brand.place')}</span>
      </div>

      {/* Phase 2. Disabled rather than hidden, so adding it does not reflow. */}
      <nav aria-label={t('mode.label')} className="flex items-center gap-0">
        {(['historical', 'forecast', 'scenario'] as const).map((m, i) => (
          <button
            key={m}
            type="button"
            disabled
            aria-disabled="true"
            className={`border border-hairline px-3 py-1 text-xs text-ink-3 ${
              i === 0 ? 'rounded-s-sm' : ''
            } ${i === 2 ? 'rounded-e-sm' : ''} ${i > 0 ? 'border-s-0' : ''}`}
            title={t('mode.phase2')}
          >
            {t(`mode.${m}`)}
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-3 text-xs">
        <ConnectionState />

        <span
          className="font-mono num text-2xs text-ink-3"
          dir="ltr"
          style={{ unicodeBidi: 'isolate' }}
          title={t('chrome.dataSourceHint')}
        >
          {DATA_SOURCE}
        </span>

        <label className="flex items-center gap-2">
          <span className="text-ink-2">{t('chrome.language')}</span>
          <select
            className="rule bg-surface px-2 py-1 text-ink"
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
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
            onChange={(e) => setTheme(e.target.value as ThemeChoice)}
          >
            <option value="system">{t('chrome.themeSystem')}</option>
            <option value="light">{t('chrome.themeLight')}</option>
            <option value="dark">{t('chrome.themeDark')}</option>
          </select>
        </label>
      </div>
    </header>
  );
}
