import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';

/** Bespoke, not a Radix Slider — and the reason is the subtlety 06 §3 names.
 *
 *  The *control* mirrors under RTL: its start edge follows reading direction.
 *  The *time axis it scrubs* does not. Earlier is always on the left, because the
 *  hyetograph beneath it runs left to right and the two must agree. Getting this
 *  backwards makes the whole time-scrub choreography feel wrong in Arabic without
 *  anyone being able to say why.
 *
 *  Radix's Slider computes its own direction from DirectionProvider and would put
 *  the minimum on the right under `dir="rtl"`. There is no prop to hold the track
 *  LTR while the surrounding layout mirrors, so this is hand-built with a real
 *  ARIA slider contract instead of fighting one.
 *
 *  Keyboard, per WAI-ARIA: arrows step, Home/End jump to the ends, PageUp/PageDown
 *  step by three. Arrow semantics stay physical — Left is earlier in both
 *  languages, matching the track.
 */
interface Props {
  steps: string[];
  value: number;
  onChange: (i: number) => void;
  /** Marks drawn on the track at their own timestamps — the mooring's onset and
   *  cleared times. These are measured, so they get a solid form. */
  marks?: Array<{ t: string; key: string; label: string }>;
}

export function TimeSlider({ steps, value, onChange, marks = [] }: Props) {
  const { t } = useTranslation();
  const track = useRef<HTMLDivElement>(null);
  const last = Math.max(0, steps.length - 1);

  const pct = (i: number) => (last === 0 ? 0 : (i / last) * 100);

  /** Position a timestamp on the track by interpolating between the steps it
   *  falls between, so a mark at 06:50 on day 3 sits between day 3 and day 4
   *  rather than snapping to one. */
  const pctForTime = (iso: string) => {
    const target = Date.parse(iso);
    const times = steps.map(Date.parse);
    if (target <= times[0]) return 0;
    if (target >= times[last]) return 100;
    const i = times.findIndex((x, k) => k < last && target >= x && target < times[k + 1]);
    if (i < 0) return 0;
    const span = times[i + 1] - times[i];
    return ((i + (target - times[i]) / span) / last) * 100;
  };

  const fromClientX = useCallback(
    (clientX: number) => {
      const el = track.current;
      if (!el || last === 0) return 0;
      const r = el.getBoundingClientRect();
      // Always measured left-to-right, never flipped for RTL — the track is the
      // time axis and the time axis does not mirror.
      const ratio = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
      return Math.round(ratio * last);
    },
    [last],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    const keys: Record<string, number> = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowDown: -1,
      ArrowUp: 1,
      PageDown: -3,
      PageUp: 3,
    };
    if (e.key === 'Home') {
      onChange(0);
    } else if (e.key === 'End') {
      onChange(last);
    } else if (e.key in keys) {
      onChange(Math.min(last, Math.max(0, value + keys[e.key])));
    } else {
      return;
    }
    e.preventDefault();
  };

  const current = steps[value];

  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      {/* The readout leads, because in a dense tool the value matters more than
          the control. Isolated and mono: it is a timestamp. */}
      <span
        dir="ltr"
        style={{ unicodeBidi: 'isolate' }}
        className="shrink-0 whitespace-nowrap font-mono num text-2xs text-ink-2"
      >
        {current?.replace('T00:00:00Z', '') ?? '—'}
      </span>

      <div
        ref={track}
        // The time axis never mirrors, so the track itself is pinned LTR while the
        // row around it follows reading direction.
        dir="ltr"
        // mx-2 so the handle at either extreme does not collide with the readouts
        // either side — at 0% and 100% it is translated -50% and overhangs the track.
        className="relative mx-2 min-w-0 flex-1 cursor-pointer py-3"
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          onChange(fromClientX(e.clientX));
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) onChange(fromClientX(e.clientX));
        }}
      >
        {/* The track is a hairline, like everything else that bounds something. */}
        <div className="h-px w-full bg-hairline-2" />

        {/* Elapsed portion, drawn as a slightly heavier hairline rather than a
            filled bar — 02 §5, the container model is lines, not blocks. */}
        <div
          className="absolute top-1/2 h-px bg-accent"
          style={{ insetInlineStart: 0, width: `${pct(value)}%` }}
        />

        {/* Step ticks. Five daily steps, so every one is drawn. */}
        {steps.map((s, i) => (
          <span
            key={s}
            aria-hidden="true"
            className={`absolute top-1/2 h-2 w-px -translate-y-1/2 ${
              i <= value ? 'bg-accent' : 'bg-hairline-2'
            }`}
            style={{ insetInlineStart: `${pct(i)}%` }}
          />
        ))}

        {/* Measured marks — solid, per the form rule in 01 §4. */}
        {marks.map((m) => (
          <span
            key={m.key}
            title={m.label}
            className="absolute top-1/2 h-4 w-px -translate-y-1/2 bg-data-measured"
            style={{ insetInlineStart: `${pctForTime(m.t)}%` }}
          >
            <span className="sr-only">{m.label}</span>
          </span>
        ))}

        {/* The handle. A real ARIA slider, not a div with a click handler. */}
        <div
          role="slider"
          tabIndex={0}
          aria-label={t('time.slider')}
          aria-valuemin={0}
          aria-valuemax={last}
          aria-valuenow={value}
          aria-valuetext={current ?? ''}
          onKeyDown={onKeyDown}
          data-time-handle="true"
          // 09: hit areas >= 24px. The visible mark is 10px, so the touch target
          // is extended with padding rather than by growing the mark.
          className="absolute top-1/2 -translate-y-1/2 p-2"
          style={{ insetInlineStart: `${pct(value)}%`, translate: '-50% -50%' }}
        >
          <span className="block h-2.5 w-2.5 rotate-45 border border-ink bg-surface" />
        </div>
      </div>

      {/* Isolated: `3/5` is two digit runs around a neutral solidus, which is the
          same bidi trap as the `0–20` range that rendered as `20–0` in the Phase 0
          specimen. Caught by the mono-run gate, not by reading it. */}
      <span
        dir="ltr"
        style={{ unicodeBidi: 'isolate' }}
        className="shrink-0 whitespace-nowrap font-mono num text-2xs text-ink-3"
      >
        {value + 1}/{steps.length}
      </span>
    </div>
  );
}
