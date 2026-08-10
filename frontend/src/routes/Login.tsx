import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { Logo } from '../components/Logo';
import { Button } from '../components/Button';
import { Field, FIELD_CLASS, fieldBorder } from '../components/Field';
import { NoticeCard } from '../components/NoticeCard';
import { AuthAside } from '../shell/MarketingChrome';
import { useAuth } from '../app/AuthContext';
import { navigate } from '../app/useRoute';

/** Sign in — transcribed from the design canvas `isLogin` block.
 *
 *  Phase 8, Track B (tasks/00-contracts.md §9): real Supabase Auth sign-in,
 *  behind the local field validation kept from the canvas. There is still no
 *  public sign-up — accounts are provisioned only after a request (Signup)
 *  is reviewed and approved out-of-band, which is why the notice at the top
 *  of the card stays permanent: most visitors genuinely won't have an
 *  account, and the dashboard staying fully open either way is the accurate
 *  claim to make, not "sign-in doesn't work."
 *
 *  Wrong email and wrong password produce the identical message — see
 *  `AuthContext.tsx` — because the user list is a short list of named
 *  institutions and confirming which credential was wrong would leak more
 *  than it should.
 *
 *  Kept from the canvas: the email format check, the required-field checks, the
 *  password reveal toggle, and the SSO affordance — the last rendered disabled,
 *  because an enabled button for an identity provider that does not exist is
 *  the same lie in a different shape.
 */

/** The canvas's own check. Deliberately loose: this is a typo catch on the
 *  client, not an address validator, and the only authority on whether an
 *  address is real is a message that arrives at it. */
function emailLooksValid(v: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M1 10 Q10 2 19 10 Q10 18 1 10 Z"
        stroke="currentColor"
        strokeWidth="1.6"
        fill="none"
      />
      {open ? (
        <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.6" fill="none" />
      ) : (
        <line x1="2" y1="18" x2="18" y2="2" stroke="currentColor" strokeWidth="1.6" />
      )}
    </svg>
  );
}

export function Login() {
  const { t } = useTranslation();
  const { signIn } = useAuth();

  const emailId = useId();
  const passwordId = useId();
  const emailErrorId = `${emailId}-error`;
  const passwordErrorId = `${passwordId}-error`;
  const noticeId = useId();
  const statusId = useId();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (pending) return; // no double-submit while a request is in flight

    const nextEmailError = !email.trim()
      ? t('auth.errors.emailRequired')
      : !emailLooksValid(email)
        ? t('auth.errors.emailInvalid')
        : null;
    const nextPasswordError = !password ? t('auth.errors.passwordRequired') : null;

    setEmailError(nextEmailError);
    setPasswordError(nextPasswordError);
    setServerError(null);
    if (nextEmailError || nextPasswordError) return;

    setPending(true);
    const { error } = await signIn(email, password);
    setPending(false);

    if (error) {
      // Never distinguish wrong email from wrong password — see AuthContext.
      setServerError(t('auth.login.invalidCredentials'));
      return;
    }
    navigate('/dashboard');
  };

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      <AuthAside
        headline={t('auth.aside.loginHeadline')}
        stats={[
          { value: t('landing.hero.stats.reefZones.value'), label: t('landing.hero.stats.reefZones.label') },
          { value: t('landing.hero.stats.forecasting.value'), label: t('landing.hero.stats.forecasting.label') },
        ]}
        foot={t('auth.aside.loginFoot')}
      />

      <main className="flex min-w-[340px] flex-1 flex-col items-center justify-center gap-6 px-5 py-12">
        <Link to="/" className="flex items-center" aria-label={t('auth.backToSite')}>
          <Logo size={27} variant="gradient" />
        </Link>

        <div className="flex w-full max-w-[420px] flex-col gap-6 rounded-card bg-surface px-8 py-10 shadow-md">
          <div className="flex flex-col gap-1.5 text-center">
            <h1 className="m-0 text-xl font-bold">{t('auth.login.title')}</h1>
            <p className="m-0 text-xs text-ink-2">{t('auth.login.subtitle')}</p>
          </div>

          {/* Permanent, not dismissible. See the file docstring. */}
          <NoticeCard id={noticeId} title={t('auth.notice.title')}>
            <p className="m-0">{t('auth.notice.body')}</p>
            <Link to="/dashboard" className="text-xs font-semibold text-accent underline">
              {t('auth.notice.openDashboard')}
            </Link>
          </NoticeCard>

          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <Field
              id={emailId}
              label={t('auth.login.email')}
              error={emailError}
              errorPrefix={t('auth.errors.prefix')}
            >
              <input
                id={emailId}
                name="email"
                type="email"
                autoComplete="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('auth.login.emailPlaceholder')}
                aria-invalid={emailError ? true : undefined}
                aria-describedby={emailError ? emailErrorId : undefined}
                className={`${FIELD_CLASS} ${fieldBorder(!!emailError)}`}
              />
            </Field>

            <Field
              id={passwordId}
              label={t('auth.login.password')}
              error={passwordError}
              errorPrefix={t('auth.errors.prefix')}
            >
              <div className="relative flex items-center">
                <input
                  id={passwordId}
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  dir="ltr"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  aria-invalid={passwordError ? true : undefined}
                  aria-describedby={passwordError ? passwordErrorId : undefined}
                  className={`${FIELD_CLASS} pe-12 ${fieldBorder(!!passwordError)}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={
                    showPassword ? t('auth.login.hidePassword') : t('auth.login.showPassword')
                  }
                  aria-pressed={showPassword}
                  aria-controls={passwordId}
                  className="absolute end-1 flex size-11 items-center justify-center rounded-sm text-ink-2 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  <EyeIcon open={showPassword} />
                </button>
              </div>
            </Field>

            {/* The canvas links this to "#". Real accounts exist now (Track
                B), but no reset flow was built — that's real, separate work,
                not something to fake with a link to nowhere. Styled as
                text, not a broken link. */}
            <p className="m-0 text-end text-xs text-ink-3">{t('auth.login.forgotPassword')}</p>

            <Button type="submit" disabled={pending} aria-describedby={noticeId}>
              {pending ? t('auth.login.pending') : t('auth.login.submit')}
            </Button>

            <p
              id={statusId}
              role="status"
              aria-live="polite"
              className={`m-0 min-h-6 text-center text-xs ${
                serverError ? 'font-semibold text-risk-critical' : 'text-ink-2'
              }`}
            >
              {serverError ?? ''}
            </p>

            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-px flex-1 bg-hairline" />
              <span className="text-xs text-ink-3">{t('auth.login.or')}</span>
              <span aria-hidden="true" className="h-px flex-1 bg-hairline" />
            </div>

            <Button type="button" variant="secondary" disabled aria-describedby={noticeId}>
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                aria-hidden="true"
                focusable="false"
              >
                <rect x="4" y="7" width="10" height="8" stroke="currentColor" strokeWidth="1.6" fill="none" />
                <line x1="9" y1="7" x2="9" y2="2" stroke="currentColor" strokeWidth="1.6" />
                <line x1="6" y1="2" x2="12" y2="2" stroke="currentColor" strokeWidth="1.6" />
              </svg>
              {t('auth.login.sso')}
            </Button>
            <p className="m-0 text-center text-xs text-ink-3">{t('auth.login.ssoUnavailable')}</p>
          </form>

          <p className="m-0 text-center text-xs text-ink-2">
            {t('auth.login.noAccess')}{' '}
            <Link to="/signup" className="font-semibold text-accent underline">
              {t('auth.login.requestAccess')}
            </Link>
          </p>
        </div>

        <Link to="/" className="py-2 text-xs font-semibold text-accent underline">
          {t('auth.backToSite')}
        </Link>
      </main>
    </div>
  );
}
