import { useTranslation } from 'react-i18next';
import { PageShell, Section, Card } from '../shell/PageShell';
import { useUi, type Lang, type ThemeChoice } from '../app/uiStore';
import { useAuth } from '../app/AuthContext';

/** Preferences, not a profile.
 *
 *  There is no authentication anywhere in this system — no accounts, no
 *  sessions, no user model, and every endpoint including the mutating ones is
 *  open. So this page deliberately shows no name, no avatar and no plan: a
 *  profile card here would be pure decoration standing in for something that
 *  does not exist, which is the failure mode the whole product is built to
 *  avoid.
 *
 *  What it does own is the two preferences that genuinely persist — language
 *  and theme. Both write through the same store the masthead uses, so a change
 *  here is a change everywhere, and uiStore mirrors them into localStorage so
 *  the choice survives a reload. */
export function AccountPage() {
  const { t } = useTranslation('tools');
  const { session } = useAuth();
  const lang = useUi((s) => s.lang);
  const setLang = useUi((s) => s.setLang);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);

  return (
    <PageShell title={t('account.title')} lede={t('account.lede')}>
      <Section label={t('account.accessSection')}>
        <Card>
          {session ? (
            <>
              {/* Real identity, once a real session exists — Phase 8, Track B.
                  Nothing here is a placeholder: this is the same verified
                  email GET /api/v1/users/me returns for this token. */}
              <h3 className="m-0 text-md font-semibold">{t('account.signedInTitle')}</h3>
              <p className="m-0 text-xs text-ink-2" dir="ltr" style={{ unicodeBidi: 'isolate' }}>
                {session.user.email}
              </p>
            </>
          ) : (
            <>
              <h3 className="m-0 text-md font-semibold">{t('account.noAuthTitle')}</h3>
              <p className="m-0 text-xs text-ink-2">{t('account.noAuthBody')}</p>
              <p className="m-0 text-xs text-ink-2">{t('account.noAuthConsequence')}</p>
            </>
          )}
        </Card>
      </Section>

      <Section label={t('account.prefsSection')}>
        <Card>
          <label className="flex flex-col gap-2" htmlFor="pref-language">
            <span className="text-xs font-semibold">{t('account.language')}</span>
            <select
              id="pref-language"
              className="rule bg-surface px-3 py-2 text-ink"
              style={{ borderRadius: 'var(--radius-md)', minBlockSize: '2.75rem' }}
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
            >
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
            <span className="text-2xs text-ink-3">{t('account.languageHint')}</span>
          </label>

          <label className="flex flex-col gap-2" htmlFor="pref-theme">
            <span className="text-xs font-semibold">{t('account.theme')}</span>
            <select
              id="pref-theme"
              className="rule bg-surface px-3 py-2 text-ink"
              style={{ borderRadius: 'var(--radius-md)', minBlockSize: '2.75rem' }}
              value={theme}
              onChange={(e) => setTheme(e.target.value as ThemeChoice)}
            >
              <option value="system">{t('account.themeSystem')}</option>
              <option value="light">{t('account.themeLight')}</option>
              <option value="dark">{t('account.themeDark')}</option>
            </select>
            <span className="text-2xs text-ink-3">{t('account.themeHint')}</span>
          </label>
        </Card>
      </Section>
    </PageShell>
  );
}
