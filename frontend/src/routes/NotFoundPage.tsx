import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { LogoMark } from '../components/Logo';

/** Rendered for an unmatched path, and for /specimen when the specimen route is
 *  disabled in a built image — so a probe for it cannot tell the difference
 *  between "not built with it" and "no such page". */
/** Type on the fixed brand gradient. It cannot be --ink-inverse: that token
 *  resolves to navy under the dark theme, and the gradient does not invert. */
const ON_GRADIENT = '#fff'; // token-ok: type on fixed brand artwork

export function NotFoundPage() {
  const { t } = useTranslation('tools');

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-canvas p-6 text-center text-ink">
      <LogoMark size={48} variant="gradient" />
      <h1 className="m-0 text-xl font-bold">{t('notFound.title')}</h1>
      <p className="m-0 max-w-prose text-xs text-ink-2">{t('notFound.body')}</p>
      <div className="flex flex-wrap items-center justify-center gap-4">
        <Link
          to="/dashboard"
          className="px-6 py-3 text-xs font-bold no-underline brand-gradient"
          style={{ borderRadius: 'var(--radius-md)', color: ON_GRADIENT }}
        >
          {t('notFound.toDashboard')}
        </Link>
        <Link
          to="/"
          className="rule px-6 py-3 text-xs font-semibold text-ink no-underline"
          style={{ borderRadius: 'var(--radius-md)' }}
        >
          {t('notFound.toHome')}
        </Link>
      </div>
    </main>
  );
}
