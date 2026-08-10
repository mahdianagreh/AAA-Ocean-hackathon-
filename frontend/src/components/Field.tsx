import type { ReactNode } from 'react';

/** The shared labelled-field wrapper — Phase 8, Track A. Both auth screens
 *  declared their own local `FIELD` constant for the 48px input styling; this
 *  is that constant's one home, plus the label/error markup that was
 *  duplicated by hand at every call site. Works for `<input>`, `<select>` and
 *  `<textarea>` alike — the input element itself is passed as `children` so
 *  this wrapper never has to know which one it is.
 *
 *  Error text stays text-first (`prefix` + message), per the file's own rule:
 *  an error a colour-blind or greyscale reader cannot see is not an error
 *  message. The themed `text-risk-critical` colour is additive, not the only
 *  signal. */
export const FIELD_CLASS =
  'h-12 w-full rounded-md border bg-surface px-4 text-sm text-ink placeholder:text-ink-3 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-accent';

export function fieldBorder(hasError: boolean): string {
  return hasError ? 'border-risk-critical' : 'border-hairline';
}

export function Field({
  id,
  label,
  optional,
  error,
  errorPrefix,
  children,
}: {
  id: string;
  label: ReactNode;
  optional?: ReactNode;
  error?: string | null;
  /** `t('auth.errors.prefix')` — kept as a real prefix word, not folded into
   *  colour, per Login.tsx's own accessibility rule. */
  errorPrefix?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold">
        {label}
        {optional ? <span className="font-normal text-ink-2"> {optional}</span> : null}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="m-0 text-xs font-semibold text-risk-critical">
          {errorPrefix ? `${errorPrefix} ` : null}
          {error}
        </p>
      ) : null}
    </div>
  );
}
