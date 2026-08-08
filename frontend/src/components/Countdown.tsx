import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/** p4-03 — 8-Hour Countdown. Client-side only, composed from an
 *  `arrival_window_hours` tuple plus the reference time it was issued
 *  against — no new endpoint. `Intl.DateTimeFormat` with an explicit IANA
 *  zone (`Asia/Jerusalem`) rather than a fixed UTC offset, because the demo
 *  event (Oct 2016) falls inside IDT (UTC+3), not IST — a hardcoded offset
 *  would be wrong for exactly this window.
 *
 *  `null` renders the honest absence, never `00:00:00` — a zeroed clock reads
 *  as "it has arrived," which is a false claim when there is simply no
 *  arrival window (e.g. Forecast mode, where no live exposure score exists
 *  yet — tasks/phase7/03-nizar.md's decision).
 */
const TIME_ZONE = 'Asia/Jerusalem';

export function Countdown({
  arrivalWindowHours,
  referenceTimeIso,
}: {
  arrivalWindowHours: [number, number] | null;
  referenceTimeIso: string | null;
}) {
  const { t } = useTranslation();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!arrivalWindowHours || !referenceTimeIso) {
    return (
      <p className="text-2xs text-ink-3" data-countdown-missing="true">
        {t('countdown.noWindow')}
      </p>
    );
  }

  const referenceMs = Date.parse(referenceTimeIso);
  const targetMs = referenceMs + arrivalWindowHours[0] * 3600_000;
  const remainingMs = targetMs - now;

  if (remainingMs <= 0) {
    return (
      <p className="text-xs text-ink-2" data-countdown-arrived="true">
        {t('countdown.arrived')}
      </p>
    );
  }

  const totalSeconds = Math.floor(remainingMs / 1000);
  const hh = Math.floor(totalSeconds / 3600);
  const mm = Math.floor((totalSeconds % 3600) / 60);
  const ss = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, '0');

  const localArrival = new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
  }).format(targetMs);

  return (
    <div className="flex flex-col gap-0.5" data-countdown="true">
      <span className="text-2xs text-ink-2">{t('countdown.label')}</span>
      <span
        dir="ltr"
        style={{ unicodeBidi: 'isolate' }}
        className="font-mono num text-lg tabular-nums text-ink"
      >
        {pad(hh)}:{pad(mm)}:{pad(ss)}
      </span>
      <span className="text-2xs text-ink-3">
        {t('countdown.localArrival', { time: localArrival })}
      </span>
    </div>
  );
}
