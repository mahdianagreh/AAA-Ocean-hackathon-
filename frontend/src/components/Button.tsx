import type { ButtonHTMLAttributes } from 'react';

/** The shared primary/secondary button — Phase 8, Track A. Login/Signup each
 *  typed `bg-ink text-ink-inverse` inline before this; a third hand-rolled
 *  copy is how a design system dies. Every variant gets a real, visible focus
 *  ring from the tokens (`Login`/`Signup` are keyboard-first screens by
 *  necessity — nothing on them is visible before a user can navigate them). */
type Variant = 'primary' | 'secondary';

const BASE =
  'flex h-12 w-full items-center justify-center gap-3 rounded-md text-sm font-bold ' +
  'transition-colors focus-visible:outline focus-visible:outline-2 ' +
  'focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed';

const VARIANT: Record<Variant, string> = {
  primary: 'bg-ink text-ink-inverse hover:opacity-90 disabled:opacity-60',
  // Secondary carries its own disabled treatment on purpose: the SSO button is
  // permanently disabled, not disabled-while-loading, and must read as a
  // deliberate absence rather than a broken control.
  secondary:
    'border-[1.5px] border-hairline-2 bg-surface text-ink-2 font-semibold ' +
    'disabled:text-ink-3 disabled:border-hairline',
};

export function Button({
  variant = 'primary',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`${BASE} ${VARIANT[variant]} ${className}`} {...rest} />;
}
