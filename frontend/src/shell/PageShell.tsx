import type { ReactNode } from 'react';

/** The standard dashboard page frame: title block, optional actions, content.
 *
 *  Every route inside DashboardChrome uses this, so heading level, max width and
 *  the 8-point rhythm are decided once. Pages that own the full viewport (the
 *  map screen) deliberately do not use it. */
export function PageShell({
  title,
  lede,
  actions,
  children,
}: {
  title: string;
  lede?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full max-w-[82rem] flex-col gap-8 p-6 lg:p-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-xl font-bold">{title}</h1>
          {lede ? <p className="m-0 text-xs text-ink-2">{lede}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </header>
      {children}
    </div>
  );
}

/** A section with a small all-caps eyebrow, matching the brand dashboard. */
export function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2
        className="m-0 text-2xs font-bold text-ink-2"
        style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }}
      >
        {label}
      </h2>
      {children}
    </section>
  );
}

/** The brand card: white surface, 20px radius, hairline border, 24px padding. */
export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col gap-3 rounded-card border border-hairline bg-surface p-6 ${className}`}
      style={{ boxShadow: 'var(--shadow-sm)' }}
    >
      {children}
    </div>
  );
}

export function CardGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid gap-5" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(15rem, 1fr))' }}>
      {children}
    </div>
  );
}
