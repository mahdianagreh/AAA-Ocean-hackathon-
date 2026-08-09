import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { Logo } from '../components/Logo';
import { AuthAside } from '../shell/MarketingChrome';

/** Request access — transcribed from the design canvas `isSignup` block.
 *
 *  Same constraint as Login: there is no auth backend, and there is no intake
 *  endpoint either. Nothing typed here leaves the browser. The canvas's
 *  "Request received" confirmation is kept because it is the designed end of
 *  the flow, but it says plainly that the request was not transmitted — a
 *  confirmation that implies a human will read it, when nothing was sent, is
 *  the same failure as a fake login wearing a friendlier face.
 *
 *  The canvas gates submission on full name and organisation being non-empty
 *  but renders no message for either, so an empty name produced a button that
 *  did nothing and said nothing. Those two now report the same way email and
 *  the agreement checkbox already did; the gate itself is unchanged.
 */

const ORG_TYPES = [
  'authority',
  'research',
  'development',
  'ngo',
  'dive',
  'other',
] as const;

function emailLooksValid(v: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

const FIELD =
  'h-12 w-full rounded-md border bg-surface px-4 text-sm text-ink placeholder:text-ink-3';

export function Signup() {
  const { t } = useTranslation();

  const nameId = useId();
  const emailId = useId();
  const orgId = useId();
  const roleId = useId();
  const orgTypeId = useId();
  const useCaseId = useId();
  const agreeId = useId();
  const noticeId = useId();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [org, setOrg] = useState('');
  const [role, setRole] = useState('');
  const [orgType, setOrgType] = useState('');
  const [useCase, setUseCase] = useState('');
  const [agree, setAgree] = useState(false);

  const [nameError, setNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [orgError, setOrgError] = useState<string | null>(null);
  const [agreeError, setAgreeError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();

    const nextName = fullName.trim() ? null : t('auth.errors.nameRequired');
    const nextEmail = !email.trim()
      ? t('auth.errors.workEmailRequired')
      : !emailLooksValid(email)
        ? t('auth.errors.emailInvalid')
        : null;
    const nextOrg = org.trim() ? null : t('auth.errors.orgRequired');
    const nextAgree = agree ? null : t('auth.errors.agreeRequired');

    setNameError(nextName);
    setEmailError(nextEmail);
    setOrgError(nextOrg);
    setAgreeError(nextAgree);

    // Local state only. No request is made — see the file docstring.
    if (!nextName && !nextEmail && !nextOrg && !nextAgree) setSubmitted(true);
  };

  const aside = (
    <AuthAside
      waveFirst
      headline={t('auth.aside.signupHeadline')}
      stats={[
        {
          value: t('landing.hero.stats.rainfall.value'),
          label: t('landing.hero.stats.rainfall.label'),
        },
        {
          value: t('landing.hero.stats.sediment.value'),
          label: t('auth.aside.sedimentLabel'),
        },
      ]}
      foot={t('auth.aside.signupFoot')}
    />
  );

  if (submitted) {
    return (
      <div className="flex min-h-screen bg-canvas text-ink">
        {aside}
        <main className="flex min-w-[340px] flex-1 flex-col items-center justify-center gap-6 px-5 py-12">
          <Link to="/" className="flex items-center" aria-label={t('auth.backToSite')}>
            <Logo size={27} variant="gradient" />
          </Link>

          <div className="flex w-full max-w-[420px] flex-col items-center gap-4 rounded-card bg-surface px-8 py-12 text-center shadow-md">
            <svg
              width="48"
              height="48"
              viewBox="0 0 48 48"
              fill="none"
              aria-hidden="true"
              focusable="false"
              className="text-accent"
            >
              <circle cx="24" cy="24" r="21" stroke="currentColor" strokeWidth="2.5" fill="none" />
              <path
                d="M14 25 L21 32 L35 16"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
            <h1 className="m-0 text-lg font-bold">{t('auth.signup.receivedTitle')}</h1>
            <p className="m-0 text-sm leading-[1.6] text-ink-2">
              {t('auth.signup.receivedBody')}
            </p>
            {/* The load-bearing sentence on this screen. */}
            <p className="m-0 rounded-md border border-hairline-2 bg-surface-2 p-4 text-xs leading-[1.6] text-ink">
              {t('auth.signup.notTransmitted')}
            </p>
            <Link to="/" className="py-2 text-xs font-semibold text-accent underline">
              {t('auth.backToSite')}
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      {aside}

      <main className="flex min-w-[340px] flex-1 flex-col items-center justify-center gap-6 px-5 py-12">
        <Link to="/" className="flex items-center" aria-label={t('auth.backToSite')}>
          <Logo size={27} variant="gradient" />
        </Link>

        <div className="flex w-full max-w-[460px] flex-col gap-5 rounded-card bg-surface px-8 py-10 shadow-md">
          <div className="flex flex-col gap-1.5 text-center">
            <h1 className="m-0 text-xl font-bold">{t('auth.signup.title')}</h1>
            <p className="m-0 text-xs leading-[1.5] text-ink-2">{t('auth.signup.subtitle')}</p>
          </div>

          <section
            id={noticeId}
            aria-labelledby={`${noticeId}-title`}
            className="flex flex-col gap-2 rounded-md border border-hairline-2 bg-surface-2 p-4"
          >
            <h2 id={`${noticeId}-title`} className="m-0 text-xs font-bold text-ink">
              {t('auth.notice.title')}
            </h2>
            <p className="m-0 text-xs leading-[1.6] text-ink-2">{t('auth.signup.noticeBody')}</p>
          </section>

          <form className="flex flex-col gap-3.5" onSubmit={onSubmit} noValidate>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={nameId} className="text-xs font-semibold">
                {t('auth.signup.fullName')}
              </label>
              <input
                id={nameId}
                name="fullName"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                aria-invalid={nameError ? true : undefined}
                aria-describedby={nameError ? `${nameId}-error` : undefined}
                className={`${FIELD} ${nameError ? 'border-risk-critical' : 'border-hairline'}`}
              />
              {nameError ? (
                <p id={`${nameId}-error`} className="m-0 text-xs font-semibold text-ink">
                  {t('auth.errors.prefix')} {nameError}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={emailId} className="text-xs font-semibold">
                {t('auth.signup.email')}
              </label>
              <input
                id={emailId}
                name="email"
                type="email"
                autoComplete="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={emailError ? true : undefined}
                aria-describedby={emailError ? `${emailId}-error` : undefined}
                className={`${FIELD} ${emailError ? 'border-risk-critical' : 'border-hairline'}`}
              />
              {emailError ? (
                <p id={`${emailId}-error`} className="m-0 text-xs font-semibold text-ink">
                  {t('auth.errors.prefix')} {emailError}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={orgId} className="text-xs font-semibold">
                {t('auth.signup.org')}
              </label>
              <input
                id={orgId}
                name="organization"
                type="text"
                autoComplete="organization"
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                aria-invalid={orgError ? true : undefined}
                aria-describedby={orgError ? `${orgId}-error` : undefined}
                className={`${FIELD} ${orgError ? 'border-risk-critical' : 'border-hairline'}`}
              />
              {orgError ? (
                <p id={`${orgId}-error`} className="m-0 text-xs font-semibold text-ink">
                  {t('auth.errors.prefix')} {orgError}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={roleId} className="text-xs font-semibold">
                {t('auth.signup.role')}
              </label>
              <input
                id={roleId}
                name="role"
                type="text"
                autoComplete="organization-title"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className={`${FIELD} border-hairline`}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={orgTypeId} className="text-xs font-semibold">
                {t('auth.signup.orgType')}
              </label>
              <select
                id={orgTypeId}
                name="orgType"
                value={orgType}
                onChange={(e) => setOrgType(e.target.value)}
                className={`${FIELD} border-hairline`}
              >
                <option value="">{t('auth.signup.orgTypeSelect')}</option>
                {ORG_TYPES.map((o) => (
                  <option key={o} value={o}>
                    {t(`auth.signup.orgTypes.${o}`)}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={useCaseId} className="text-xs font-semibold">
                {t('auth.signup.useCase')}{' '}
                <span className="font-normal text-ink-2">{t('auth.signup.optional')}</span>
              </label>
              <textarea
                id={useCaseId}
                name="useCase"
                rows={3}
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                className="w-full resize-y rounded-md border border-hairline bg-surface px-4 py-3 text-sm text-ink"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-start gap-3">
                <input
                  id={agreeId}
                  name="agree"
                  type="checkbox"
                  checked={agree}
                  onChange={(e) => setAgree(e.target.checked)}
                  aria-invalid={agreeError ? true : undefined}
                  aria-describedby={agreeError ? `${agreeId}-error` : undefined}
                  className="mt-1 size-6 shrink-0 accent-accent"
                />
                <label htmlFor={agreeId} className="text-xs leading-[1.5] text-ink-2">
                  {t('auth.signup.agree')}
                </label>
              </div>
              {agreeError ? (
                <p id={`${agreeId}-error`} className="m-0 text-xs font-semibold text-ink">
                  {t('auth.errors.prefix')} {agreeError}
                </p>
              ) : null}
            </div>

            <button
              type="submit"
              aria-describedby={noticeId}
              className="mt-1 h-12 w-full rounded-md bg-ink text-sm font-bold text-ink-inverse"
            >
              {t('auth.signup.submit')}
            </button>
          </form>

          <p className="m-0 text-center text-xs text-ink-2">
            {t('auth.signup.haveAccess')}{' '}
            <Link to="/login" className="font-semibold text-accent underline">
              {t('auth.signup.signIn')}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
