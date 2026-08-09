import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from '../components/Link';
import { Logo } from '../components/Logo';
import { Button } from '../components/Button';
import { Field, FIELD_CLASS, fieldBorder } from '../components/Field';
import { NoticeCard } from '../components/NoticeCard';
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
  const notTransmittedId = useId();

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
            {/* Not a checkmark on purpose — a checkmark reads as "done,
                succeeded," and this form was validated locally, not sent
                anywhere. A recorded-document glyph makes a different, true
                claim: "noted here," not "delivered." */}
            <svg
              width="48"
              height="48"
              viewBox="0 0 48 48"
              fill="none"
              aria-hidden="true"
              focusable="false"
              className="text-accent"
            >
              <rect x="12" y="7" width="24" height="34" rx="2" stroke="currentColor" strokeWidth="2.5" fill="none" />
              <line x1="18" y1="17" x2="30" y2="17" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
              <line x1="18" y1="24" x2="30" y2="24" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
              <line x1="18" y1="31" x2="25" y2="31" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            </svg>
            <h1 className="m-0 text-lg font-bold">{t('auth.signup.receivedTitle')}</h1>
            <p className="m-0 text-sm leading-[1.6] text-ink-2">
              {t('auth.signup.receivedBody')}
            </p>
            {/* The load-bearing sentence on this screen — full NoticeCard
                treatment, not fine print under a success symbol. */}
            <NoticeCard id={notTransmittedId} title={t('auth.signup.notTransmittedTitle')}>
              <p className="m-0 text-start">{t('auth.signup.notTransmitted')}</p>
            </NoticeCard>
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

          <NoticeCard id={noticeId} title={t('auth.notice.title')}>
            <p className="m-0">{t('auth.signup.noticeBody')}</p>
          </NoticeCard>

          <form className="flex flex-col gap-3.5" onSubmit={onSubmit} noValidate>
            <Field
              id={nameId}
              label={t('auth.signup.fullName')}
              error={nameError}
              errorPrefix={t('auth.errors.prefix')}
            >
              <input
                id={nameId}
                name="fullName"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                aria-invalid={nameError ? true : undefined}
                aria-describedby={nameError ? `${nameId}-error` : undefined}
                className={`${FIELD_CLASS} ${fieldBorder(!!nameError)}`}
              />
            </Field>

            <Field
              id={emailId}
              label={t('auth.signup.email')}
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
                aria-invalid={emailError ? true : undefined}
                aria-describedby={emailError ? `${emailId}-error` : undefined}
                className={`${FIELD_CLASS} ${fieldBorder(!!emailError)}`}
              />
            </Field>

            <Field
              id={orgId}
              label={t('auth.signup.org')}
              error={orgError}
              errorPrefix={t('auth.errors.prefix')}
            >
              <input
                id={orgId}
                name="organization"
                type="text"
                autoComplete="organization"
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                aria-invalid={orgError ? true : undefined}
                aria-describedby={orgError ? `${orgId}-error` : undefined}
                className={`${FIELD_CLASS} ${fieldBorder(!!orgError)}`}
              />
            </Field>

            {/* Optional, and now visibly so before submission — role and
                org type used to be indistinguishable from the required
                fields until a successful submit proved otherwise. */}
            <Field id={roleId} label={t('auth.signup.role')} optional={t('auth.signup.optional')}>
              <input
                id={roleId}
                name="role"
                type="text"
                autoComplete="organization-title"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className={`${FIELD_CLASS} border-hairline`}
              />
            </Field>

            <Field
              id={orgTypeId}
              label={t('auth.signup.orgType')}
              optional={t('auth.signup.optional')}
            >
              <select
                id={orgTypeId}
                name="orgType"
                value={orgType}
                onChange={(e) => setOrgType(e.target.value)}
                className={`${FIELD_CLASS} border-hairline`}
              >
                <option value="">{t('auth.signup.orgTypeSelect')}</option>
                {ORG_TYPES.map((o) => (
                  <option key={o} value={o}>
                    {t(`auth.signup.orgTypes.${o}`)}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              id={useCaseId}
              label={t('auth.signup.useCase')}
              optional={t('auth.signup.optional')}
            >
              <textarea
                id={useCaseId}
                name="useCase"
                rows={3}
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                className="w-full resize-y rounded-md border border-hairline bg-surface px-4 py-3 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
            </Field>

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
                  className="mt-1 size-6 shrink-0 accent-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                />
                <label htmlFor={agreeId} className="text-xs leading-[1.5] text-ink-2">
                  {t('auth.signup.agree')}
                </label>
              </div>
              {agreeError ? (
                <p id={`${agreeId}-error`} className="m-0 text-xs font-semibold text-risk-critical">
                  {t('auth.errors.prefix')} {agreeError}
                </p>
              ) : null}
            </div>

            <Button type="submit" aria-describedby={noticeId} className="mt-1">
              {t('auth.signup.submit')}
            </Button>
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
