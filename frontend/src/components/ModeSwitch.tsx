import { ToggleGroup } from 'radix-ui';
import { useTranslation } from 'react-i18next';
import type { Mode } from '../app/uiStore';

const MODES: Mode[] = ['historical', 'forecast', 'scenario'];

/** Radix Toggle Group, styled through tokens.
 *
 *  Radix supplies what is genuinely hard: roving tabindex, arrow-key navigation
 *  that respects direction via DirectionProvider, and the correct
 *  `role="group"` + `aria-pressed` semantics. Hand-rolling that is how a control
 *  ends up keyboard-inaccessible while looking finished.
 *
 *  Unlike the time slider, this one *should* mirror in RTL — it is navigation, not
 *  a time axis, and 06 §3 lists navigation under "mirrors".
 */
export function ModeSwitch({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (m: Mode) => void;
}) {
  const { t } = useTranslation();

  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(v) => {
        // Radix emits '' when the pressed item is deselected. Three modes are
        // exhaustive and one is always active, so ignore the empty case rather
        // than letting the view fall into no mode at all.
        if (v) onChange(v as Mode);
      }}
      aria-label={t('mode.label')}
      className="flex items-center"
    >
      {MODES.map((m, i) => (
        <ToggleGroup.Item
          key={m}
          value={m}
          data-mode={m}
          className={[
            'border border-hairline px-3 py-1 text-xs text-ink-2',
            'data-[state=on]:border-accent data-[state=on]:text-ink',
            'data-[state=on]:bg-surface-2',
            'focus-visible:z-10',
            // Logical radii and borders, so the group joins correctly in both
            // directions. `rounded-l` would be wrong under RTL.
            i === 0 ? 'rounded-s-sm' : '',
            i === MODES.length - 1 ? 'rounded-e-sm' : '',
            i > 0 ? 'border-s-0' : '',
          ].join(' ')}
        >
          {t(`mode.${m}`)}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
